"""投研情报 Agent · v0.1（FastAPI）

设计原则：
1. 数值与事实只来自抓取到的原文，模型只做摘要、打标与行文，不做任何投资判断；
2. 所有输出末尾强制附加 _shared/disclaimer.txt；
3. 输出前按 _shared/high_risk_words.txt 做高危词过滤/打码，保证合规自检通过；
4. 存储只用本地文件（Markdown + JSONL），不引任何数据库；
5. 密钥只从环境变量/请求体读取，绝不落盘、绝不硬编码。
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from openai import OpenAI
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 路径：全部基于本文件位置推导，禁止绝对路径硬编码（发布沙箱要求）
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
TRACE_FILE = BASE_DIR / "trace.jsonl"
SHARED_DIR = ROOT_DIR / "_shared"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(ROOT_DIR / ".env", override=False)
load_dotenv(BASE_DIR / ".env", override=False)

SYSTEM_PROMPT = (SHARED_DIR / "system_prompt.txt").read_text(encoding="utf-8").strip()
DISCLAIMER = (SHARED_DIR / "disclaimer.txt").read_text(encoding="utf-8").strip()

MODEL = os.getenv("ZHIPU_MODEL", "glm-4.5-flash")
BASE_URL = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
API_KEY = os.getenv("ZHIPU_API_KEY", "").strip()
CST = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# 价格表（元 / 百万 tokens），来源：open.bigmodel.cn/pricing（2026-10-16 核实）
# glm-4.7-flash 官方明确"输入免费、输出免费、缓存免费"。换模型时改这张表即可。
# 未列出的模型按 0 计并在 /stats 里标注 price_source=unknown。
# ---------------------------------------------------------------------------
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "glm-4.7-flash": (0.0, 0.0),
    "glm-4.5-flash": (0.6, 1.8),      # 未在本期价格页列出，沿用公开档估算
    "glm-5.3-flash": (0.8, 2.8),
    "glm-5.2": (8.0, 28.0),
}

# 信源为 2026-10-16 实测可抓、且条目为当日更新的公开 RSS。
# 注：新浪财经 rollnews RSS 实测返回 2008 年的陈旧条目，会被新鲜度过滤丢弃，故不列入。
SOURCES: list[dict[str, str]] = [
    {"name": "中新网·财经", "url": "https://www.chinanews.com.cn/rss/finance.xml"},
    {"name": "中新网·要闻", "url": "https://www.chinanews.com.cn/rss/importnews.xml"},
    {"name": "中新网·滚动", "url": "https://www.chinanews.com.cn/rss/scroll-news.xml"},
]
MAX_ARTICLES = 4  # 免费档并发约 1，串行调用，控制单次成本与耗时
CALL_INTERVAL_S = 1.5
FRESH_DAYS = 7  # 只要近 7 日条目，避免信源返回陈旧内容

# 离线兜底数据：明确标注为示例，避免与真实新闻混淆
FALLBACK_ARTICLES: list[dict[str, str]] = [
    {
        "source": "内置示例数据（离线兜底）",
        "title": "示例条目一：公开市场操作与流动性投放口径调整",
        "link": "https://example.com/demo-1",
        "published": "",
        "summary": "【示例数据，非真实新闻】用于演示离线环境下的完整链路：抓取→清洗→摘要→成稿。",
    },
    {
        "source": "内置示例数据（离线兜底）",
        "title": "示例条目二：某行业季度产能利用率披露口径变更",
        "link": "https://example.com/demo-2",
        "published": "",
        "summary": "【示例数据，非真实新闻】用于验证摘要与标签（利好/中性/风险）链路可用。",
    },
    {
        "source": "内置示例数据（离线兜底）",
        "title": "示例条目三：跨境结算便利化试点范围扩大",
        "link": "https://example.com/demo-3",
        "published": "",
        "summary": "【示例数据，非真实新闻】用于验证简报落盘、trace 记录与合规过滤。",
    },
]

TAG_ORDER = {"利好": 0, "中性": 1, "风险": 2}


def load_high_risk_words() -> list[str]:
    """读取高危词表，跳过 # 注释与空行。"""
    path = SHARED_DIR / "high_risk_words.txt"
    if not path.exists():
        return []
    words: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words.append(line)
    return words


HIGH_RISK_WORDS = load_high_risk_words()


def scan_high_risk(text: str) -> list[str]:
    return [w for w in HIGH_RISK_WORDS if w and w in text]


def mask_high_risk(text: str) -> tuple[str, list[str]]:
    """兜底打码：把命中的高危词替换为 ◼◼，返回（新文本，命中词列表）。"""
    hits = scan_high_risk(text)
    if not hits:
        return text, []
    for w in sorted(set(hits), key=len, reverse=True):
        text = text.replace(w, "◼◼")
    return text, hits


# ---------------------------------------------------------------------------
# 抓取与清洗
# ---------------------------------------------------------------------------
def parse_pub_date(raw: str, entry) -> datetime | None:
    """解析 RSS 发布时间，解析失败返回 None（调用方会丢弃该条目）。"""
    tp = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if tp:
        try:
            return datetime(*tp[:6], tzinfo=timezone.utc).astimezone(CST)
        except Exception:
            pass
    if raw:
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(raw)
            return dt.astimezone(CST) if dt.tzinfo else dt.replace(tzinfo=CST)
        except Exception:
            pass
    return None


def fetch_articles(per_source: int = 3, timeout: int = 8) -> tuple[list[dict], list[str], bool]:
    """抓取 RSS。返回（文章列表，错误列表，是否使用了兜底数据）。"""
    articles: list[dict] = []
    errors: list[str] = []
    for src in SOURCES:
        try:
            resp = requests.get(
                src["url"],
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (invest-intel-agent/0.1)"},
            )
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            entries = list(feed.entries)[:per_source]
            if not entries:
                errors.append(f"{src['name']}：RSS 解析为空")
                continue
            fresh = 0
            for e in entries:
                pub_raw = (e.get("published") or e.get("updated") or "").strip()
                dt = parse_pub_date(pub_raw, e)
                if dt is None:
                    continue  # 无法判定发布时间的条目直接丢弃，避免陈旧内容混入
                if (datetime.now(CST) - dt).days > FRESH_DAYS:
                    continue
                fresh += 1
                articles.append(
                    {
                        "source": src["name"],
                        "title": (e.get("title") or "").strip(),
                        "link": (e.get("link") or "").strip(),
                        "published": dt.strftime("%Y-%m-%d %H:%M"),
                        "summary": re.sub(r"<[^>]+>", "", (e.get("summary") or ""))[:400].strip(),
                    }
                )
            if fresh == 0:
                errors.append(f"{src['name']}：无 {FRESH_DAYS} 日内更新条目")
        except Exception as exc:  # 单源失败不影响整体
            errors.append(f"{src['name']}：{type(exc).__name__}")

    # 清洗：去空标题、去重（标题+链接）
    cleaned: list[dict] = []
    seen: set[str] = set()
    for a in articles:
        if not a["title"]:
            continue
        key = a["title"][:60]
        if key in seen:
            continue
        seen.add(key)
        a["title"], hit_title = mask_high_risk(a["title"])
        a["summary"], hit_sum = mask_high_risk(a["summary"])
        if hit_title:
            errors.append(f"高危词过滤（标题）：{','.join(sorted(set(hit_title)))}")
        cleaned.append(a)

    used_fallback = False
    if len(cleaned) < 3:
        cleaned = [dict(x) for x in FALLBACK_ARTICLES]
        used_fallback = True
        errors.append(f"信源不足 3 条，已切换内置示例数据（信源错误 {len(errors)} 项）")
    return cleaned[:MAX_ARTICLES], errors, used_fallback


# ---------------------------------------------------------------------------
# 模型调用
# ---------------------------------------------------------------------------
def build_client(api_key: str | None = None) -> OpenAI:
    key = (api_key or API_KEY).strip()
    if not key:
        raise RuntimeError("未配置 ZHIPU_API_KEY：请在环境变量或请求体中提供 API Key")
    return OpenAI(api_key=key, base_url=BASE_URL, timeout=60.0, max_retries=1)


def chat(system: str, user: str, max_tokens: int = 1024, api_key: str | None = None) -> tuple[str, dict]:
    """调用模型。两个已实测的坑：
    1) glm flash 系列默认带思考输出，max_tokens 太小会返回空正文 → 关闭 thinking，
       仍为空则把 max_tokens 翻倍重试；
    2) 免费档并发约 1，短时多调会返回 429「该模型当前访问量过大」→ 指数退避重试。
    取值只用 message.content，不用 reasoning_content。"""
    client = build_client(api_key)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last = ""
    for attempt in range(4):
        mt = max_tokens if attempt < 2 else max_tokens * 2
        kwargs: dict = {}
        # 前两次关掉思考输出（省 token、避免正文被思考挤空）；
        # 部分模型（如 glm-5.3-flash）不支持关闭思考，会在后两次自动去掉该参数重试。
        if attempt < 2:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=mt,
                temperature=0.3,
                **kwargs,
            )
            content = resp.choices[0].message.content or ""
            usage = {
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(resp.usage, "total_tokens", 0) or 0,
            }
            if content.strip():
                return content.strip(), usage
            last = "模型返回空内容（思考输出占满 max_tokens）"
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(1 + 2 * attempt)
    raise RuntimeError(f"模型调用失败（已重试 4 次）：{last}")


def rule_based_summary(article: dict) -> str:
    """模型限流/不可用时的兜底摘录：取原文摘要首句，不编造内容。"""
    text = re.sub(r"【[^】]*】", "", article.get("summary") or "").strip()
    snippet = re.split(r"[。！？\n]", text)[0].strip()
    if not snippet:
        snippet = article.get("title", "")
    if len(snippet) > 80:
        snippet = snippet[:80] + "…"
    return snippet or "（暂无可用摘要）"


def estimate_tokens(text: str) -> int:
    """无 usage 时按字符数粗估：中文约 1.5 字符/token。"""
    return max(1, int(len(text) / 1.5))


def summarize_article(article: dict, api_key: str | None = None) -> tuple[dict, dict]:
    user = (
        "请基于下面这条资讯做整理，严格只输出一行 JSON，不要任何解释、不要 Markdown 代码块：\n"
        '{"tag": "利好|中性|风险", "summary": "80 字以内的客观摘要，只陈述事实"}\n'
        "打标规则：只有原文明确表述正面影响才标【利好】；明确表述负面影响、违规、下滑、"
        "警示才标【风险】；无法判断或中性事实一律标【中性】。不确定时不要标利好。\n\n"
        f"标题：{article['title']}\n"
        f"来源：{article['source']}\n"
        f"原文摘要：{article['summary'][:300]}\n"
    )
    raw, usage = chat(SYSTEM_PROMPT, user, max_tokens=1024, api_key=api_key)
    tag, summary = "中性", ""
    m = re.search(r"\{[^{}]*\}", raw, flags=re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            tag = str(data.get("tag", "中性")).strip()
            summary = str(data.get("summary", "")).strip()
        except Exception:
            pass
    if tag not in TAG_ORDER:
        tag = "中性"
    if not summary:
        summary = raw[:80]
    summary = summary.replace("\n", " ").strip()
    if len(summary) > 80:
        summary = summary[:80] + "…"
    summary, hits = mask_high_risk(summary)
    out = dict(article)
    out["tag"] = tag
    out["summary"] = summary
    out["filtered_words"] = hits
    return out, usage


# ---------------------------------------------------------------------------
# 简报生成
# ---------------------------------------------------------------------------
def render_brief(items: list[dict], sources: int, used_fallback: bool, errors: list[str]) -> str:
    today = datetime.now(CST).strftime("%Y-%m-%d")
    lines: list[str] = []
    lines.append(f"# 投研情报简报 · {today}")
    lines.append("")
    data_note = "（本次使用内置示例数据，非真实新闻）" if used_fallback else ""
    lines.append(
        f"> 生成时间：{datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}（北京时间）　"
        f"信源：{sources} 个　条目：{len(items)} 条{data_note}"
    )
    lines.append("")

    lines.append("## 一、今日要点")
    for it in items[:5]:
        lines.append(f"- 【{it['tag']}】{it['title']}")
    lines.append("")

    lines.append("## 二、分条摘要")
    for idx, it in enumerate(items, 1):
        lines.append(f"### {idx}. 【{it['tag']}】{it['title']}")
        lines.append("")
        lines.append(it["summary"] or "（模型未返回摘要）")
        lines.append("")
        pub = f"　发布时间：{it['published']}" if it.get("published") else ""
        lines.append(f"- 来源：{it['source']}{pub}")
        if it.get("link"):
            lines.append(f"- 原文：[{it['link']}]({it['link']})")
        lines.append("")

    risky = [it for it in items if it["tag"] == "风险"]
    lines.append("## 三、风险与非正面条目")
    if risky:
        for it in risky:
            lines.append(f"- {it['title']}：{it['summary']}")
    else:
        lines.append("- 本次未标记风险条目。")
    lines.append("")

    if errors:
        lines.append("## 四、运行提示")
        for e in errors[:10]:
            lines.append(f"- {e}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")
    return "\n".join(lines)


def append_trace(row: dict) -> None:
    with TRACE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def cost_of(model: str, prompt_tokens: int, completion_tokens: int) -> tuple[float, str]:
    price = PRICE_TABLE.get(model)
    if price is None:
        return 0.0, "unknown"
    return round(prompt_tokens / 1_000_000 * price[0] + completion_tokens / 1_000_000 * price[1], 6), "price_table"


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------
app = FastAPI(
    title="投研情报 Agent",
    version="0.1.0",
    description="抓取多信源 → 清洗去重 → LLM 摘要打标 → 生成合规情报简报（仅供参考，不构成投资建议）",
)


class RunRequest(BaseModel):
    api_key: str | None = Field(default=None, description="可选：本次请求临时使用的 API Key，仅内存中使用，不落盘")
    per_source: int = Field(default=2, ge=1, le=5)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>投研情报 Agent</title>
<style>
body{font-family:-apple-system,"PingFang SC",sans-serif;max-width:720px;margin:40px auto;padding:0 16px;line-height:1.7;color:#222}
button{background:#1a6fd4;color:#fff;border:0;border-radius:6px;padding:10px 20px;font-size:15px;cursor:pointer}
button:disabled{background:#999} pre{background:#f6f8fa;padding:12px;border-radius:6px;overflow:auto;white-space:pre-wrap}
input{width:100%;padding:8px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box}
.tip{color:#666;font-size:13px}
</style></head><body>
<h1>投研情报 Agent</h1>
<p>点击按钮：抓取多信源 → 清洗去重 → 大模型摘要打标 → 生成一份带免责声明的 Markdown 简报。</p>
<p class="tip">未配置 Key 时可在此临时填写（仅本次请求内存中使用，不保存）：</p>
<input id="k" placeholder="留空则使用服务端环境变量中的 Key" />
<p><button id="b" onclick="run()">生成今日简报</button></p>
<pre id="o">等待操作…</pre>
<script>
async function run(){
  const b=document.getElementById('b'),o=document.getElementById('o');
  b.disabled=true;o.textContent='运行中，约需 20-60 秒…';
  try{
    const body={};const k=document.getElementById('k').value.trim();if(k)body.api_key=k;
    const r=await fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    o.textContent=r.ok?('已生成：'+j.file+'\\n条目：'+j.articles+' 条\\n耗时：'+j.elapsed_s+' 秒\\n预估成本：'+j.cost_yuan+' 元\\n\\n'+j.content.slice(0,1200)+'\\n…'):JSON.stringify(j,null,2);
  }catch(e){o.textContent='请求失败：'+e}
  b.disabled=false;
}
</script></body></html>"""


@app.post("/run")
def run(req: RunRequest):
    started = time.time()
    # 快速失败：没有 Key 就不要白抓一遍（发布环境下用户可自己在页面填入）
    if not (req.api_key or "").strip() and not API_KEY:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "未配置 API Key。请在页面输入框中填写智谱 API Key（仅本次请求内存使用，不保存），"
                "或设置环境变量 ZHIPU_API_KEY。",
                "hint": "获取地址：https://open.bigmodel.cn/",
            },
        )
    articles, errors, used_fallback = fetch_articles(per_source=req.per_source)
    sources_ok = len([s for s in SOURCES if not any(s["name"] in e for e in errors)])

    items: list[dict] = []
    total_prompt = 0
    total_completion = 0
    for idx, a in enumerate(articles):
        if idx:
            time.sleep(CALL_INTERVAL_S)  # 免费档并发约 1，串行限速
        try:
            item, usage = summarize_article(a, api_key=req.api_key)
            total_prompt += usage["prompt_tokens"]
            total_completion += usage["completion_tokens"]
        except Exception as exc:
            errors.append(f"摘要降级为规则摘录：{exc}")
            item = dict(a)
            item["tag"] = "中性"
            item["summary"] = rule_based_summary(a) + "（模型限流，已回退为规则摘录）"
        items.append(item)

    items.sort(key=lambda x: TAG_ORDER.get(x["tag"], 1))
    content = render_brief(items, sources_ok, used_fallback, errors)
    content, hits = mask_high_risk(content)

    if not total_prompt:
        total_prompt = sum(estimate_tokens(SYSTEM_PROMPT + a["title"] + a["summary"]) for a in articles)
        total_completion = sum(estimate_tokens(i["summary"]) for i in items)
    cost, price_source = cost_of(MODEL, total_prompt, total_completion)

    fname = f"brief_{datetime.now(CST).strftime('%Y%m%d')}.md"
    path = OUTPUT_DIR / fname
    path.write_text(content, encoding="utf-8")

    row = {
        "ts": datetime.now(CST).isoformat(timespec="seconds"),
        "model": MODEL,
        "sources": sources_ok,
        "articles": len(items),
        "prompt_tokens": total_prompt,
        "completion_tokens": total_completion,
        "total_tokens": total_prompt + total_completion,
        "elapsed_s": round(time.time() - started, 2),
        "cost_yuan": cost,
        "price_source": price_source,
        "file": fname,
        "fallback": used_fallback,
        "masked_words": sorted(set(hits)),
        "errors": errors[:5],
    }
    append_trace(row)
    return {
        "file": str(path.relative_to(BASE_DIR)),
        "articles": len(items),
        "sources": sources_ok,
        "elapsed_s": row["elapsed_s"],
        "tokens": row["total_tokens"],
        "cost_yuan": cost,
        "fallback": used_fallback,
        "errors": errors[:5],
        "content": content,
    }


@app.get("/latest")
def latest():
    files = sorted(OUTPUT_DIR.glob("brief_*.md"))
    if not files:
        return PlainTextResponse("尚未生成简报，请先调用 POST /run", status_code=404)
    return PlainTextResponse(files[-1].read_text(encoding="utf-8"))


@app.get("/stats")
def stats():
    runs, articles, prompt_t, completion_t, tokens, elapsed, cost = 0, 0, 0, 0, 0, 0.0, 0.0
    if TRACE_FILE.exists():
        for line in TRACE_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            runs += 1
            articles += int(r.get("articles", 0))
            prompt_t += int(r.get("prompt_tokens", 0))
            completion_t += int(r.get("completion_tokens", 0))
            tokens += int(r.get("total_tokens", 0))
            elapsed += float(r.get("elapsed_s", 0))
            cost += float(r.get("cost_yuan", 0))
    avg = round(elapsed / runs, 2) if runs else 0.0
    return {
        "total_runs": runs,
        "total_articles": articles,
        "total_prompt_tokens": prompt_t,
        "total_completion_tokens": completion_t,
        "total_tokens": tokens,
        "total_elapsed_s": round(elapsed, 2),
        "avg_elapsed_s": avg,
        "estimated_cost_yuan": round(cost, 4),
        "per_run_cost_yuan": round(cost / runs, 4) if runs else 0.0,
        "model": MODEL,
        "price_source": PRICE_TABLE.get(MODEL) and "price_table" or "unknown",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL,
        "api_key_configured": bool(API_KEY),
        "disclaimer_loaded": bool(DISCLAIMER),
        "high_risk_words": len(HIGH_RISK_WORDS),
    }


@app.exception_handler(RuntimeError)
def runtime_error_handler(request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# 发布形态：单端口 + 从环境变量读 PORT（发布沙箱会注入 PORT）
# 本地：python app.py；线上：PORT=8080 python app.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
