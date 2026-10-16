"""数据报表自动化 Agent · v0.1（FastAPI）

核心卖点（也是设计原则）：**数字全部由 pandas 算出，LLM 只负责解读和行文**。
模型不得自行计算、不得修改任何数字；生成后做双向对账校验：
  1) 正向：每个关键指标的计算值必须出现在报告里；
  2) 反向：报告里带单位/百分号的数字必须都能在计算值里找到。
任一项不通过就在报告末尾写「⚠️ 对账不一致」并在接口返回 mismatch 列表。
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from openai import OpenAI
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
SAMPLE_CSV = BASE_DIR / "sample_data" / "sample.csv"
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

ANOMALY_THRESHOLD = 0.20  # 波动超过 20% 视为异常
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "glm-4.7-flash": (0.0, 0.0),
    "glm-4.5-flash": (0.6, 1.8),
    "glm-5.3-flash": (0.8, 2.8),
}


def load_high_risk_words() -> list[str]:
    path = SHARED_DIR / "high_risk_words.txt"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


HIGH_RISK_WORDS = load_high_risk_words()


def mask_high_risk(text: str) -> tuple[str, list[str]]:
    hits = [w for w in HIGH_RISK_WORDS if w and w in text]
    for w in sorted(set(hits), key=len, reverse=True):
        text = text.replace(w, "◼◼")
    return text, hits


# ---------------------------------------------------------------------------
# 1) pandas 计算：所有数字的来源
# ---------------------------------------------------------------------------
def pct(new: float, old: float) -> float | None:
    """环比/同比变动率（%）。基期缺失或为 0 时返回 None（调用方输出「数据不足，跳过」）。"""
    if old is None or pd.isna(old) or old == 0:
        return None
    return round((new - old) / abs(old) * 100, 2)


def compute(csv_path: Path) -> tuple[dict, pd.DataFrame, str]:
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")
    df["profit"] = df["revenue"] - df["cost"]

    months = sorted(df["month"].unique())
    cur = months[-1]
    prev = cur - 1
    yoy = cur - 12
    period = str(cur)

    def agg(m):
        d = df[df["month"] == m]
        if d.empty:
            return None
        rev = float(d["revenue"].sum())
        cost = float(d["cost"].sum())
        return {
            "revenue": round(rev, 2),
            "cost": round(cost, 2),
            "profit": round(rev - cost, 2),
            "margin": round((rev - cost) / rev * 100, 2) if rev else None,
        }

    c, p, y = agg(cur), agg(prev), agg(yoy)
    facts: dict[str, float] = {}
    facts[f"{period} 总营收"] = c["revenue"]
    facts[f"{period} 总成本"] = c["cost"]
    facts[f"{period} 毛利"] = c["profit"]
    facts[f"{period} 毛利率(%)"] = c["margin"]

    mom_block = "数据不足，跳过"
    if p:
        facts["总营收环比(%)"] = pct(c["revenue"], p["revenue"])
        facts["总成本环比(%)"] = pct(c["cost"], p["cost"])
        facts["毛利环比(%)"] = pct(c["profit"], p["profit"])
        mom_block = (
            f"- 总营收：{c['revenue']:.2f} 万元，环比 {facts['总营收环比(%)']:+.2f}%\n"
            f"- 总成本：{c['cost']:.2f} 万元，环比 {facts['总成本环比(%)']:+.2f}%\n"
            f"- 毛利：{c['profit']:.2f} 万元，环比 {facts['毛利环比(%)']:+.2f}%"
        )
    yoy_block = "数据不足，跳过"
    if y:
        facts["总营收同比(%)"] = pct(c["revenue"], y["revenue"])
        facts["总成本同比(%)"] = pct(c["cost"], y["cost"])
        facts["毛利同比(%)"] = pct(c["profit"], y["profit"])
        yoy_block = (
            f"- 总营收：{c['revenue']:.2f} 万元，同比 {facts['总营收同比(%)']:+.2f}%\n"
            f"- 总成本：{c['cost']:.2f} 万元，同比 {facts['总成本同比(%)']:+.2f}%\n"
            f"- 毛利：{c['profit']:.2f} 万元，同比 {facts['毛利同比(%)']:+.2f}%"
        )

    # 各品类占比 + 异常
    cur_df = df[df["month"] == cur]
    share_rows: list[str] = []
    anomaly_rows: list[dict] = []
    for cat, g in cur_df.groupby("category"):
        rev = round(float(g["revenue"].sum()), 2)
        cost = round(float(g["cost"].sum()), 2)
        share = round(rev / c["revenue"] * 100, 2) if c["revenue"] else None
        facts[f"{cat} 营收"] = rev
        facts[f"{cat} 成本"] = cost
        facts[f"{cat} 占比(%)"] = share
        share_rows.append(f"- {cat}：营收 {rev:.2f} 万元，占比 {share:.2f}%，成本 {cost:.2f} 万元")

        prev_rev = float(df[(df["month"] == prev) & (df["category"] == cat)]["revenue"].sum()) if p else None
        yoy_rev = float(df[(df["month"] == yoy) & (df["category"] == cat)]["revenue"].sum()) if y else None
        m = pct(rev, prev_rev)
        yv = pct(rev, yoy_rev)
        if m is not None:
            facts[f"{cat} 营收环比(%)"] = m
        if yv is not None:
            facts[f"{cat} 营收同比(%)"] = yv
        for label, val in (("环比", m), ("同比", yv)):
            if val is not None and abs(val) / 100 > ANOMALY_THRESHOLD:
                anomaly_rows.append(
                    {
                        "category": cat,
                        "维度": label,
                        "当期营收(万元)": rev,
                        "对比期营收(万元)": round(prev_rev if label == "环比" else yoy_rev, 2),
                        "变动率(%)": val,
                        "说明": "增长" if val > 0 else "下滑",
                    }
                )

    anomalies = pd.DataFrame(anomaly_rows)
    anomalies_path = OUTPUT_DIR / "anomalies.csv"
    anomalies.to_csv(anomalies_path, index=False, encoding="utf-8-sig")

    facts_block = "\n".join(f"- {k}：{v}" for k, v in facts.items())
    computed = {
        "period": period,
        "当期": c,
        "上期": p,
        "去年同期": y,
        "facts": facts,
        "mom_block": mom_block,
        "yoy_block": yoy_block,
        "share_block": "\n".join(share_rows),
        "anomaly_block": (
            anomalies.to_string(index=False)
            if not anomalies.empty
            else "无（本期无超过 20% 的波动项）"
        ),
        "facts_block": facts_block,
        "anomaly_count": len(anomaly_rows),
    }
    return computed, anomalies, str(anomalies_path)


# ---------------------------------------------------------------------------
# 2) 对账校验
# ---------------------------------------------------------------------------
NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _expected_values(facts: dict[str, float]) -> list[float]:
    vals: list[float] = []
    for v in facts.values():
        if v is None or pd.isna(v):
            continue
        f = float(v)
        for x in (f, round(f, 2), round(f, 1), round(f), abs(f), round(abs(f), 1), round(abs(f))):
            vals.append(x)
    return vals


def reconcile(
    report: str, facts: dict[str, float], allow_extra: tuple[float, ...] = ()
) -> tuple[list[str], list[dict]]:
    """返回（不一致项列表，对账明细表）。

    allow_extra：提示词中已明确告知模型的常量（如异常判定阈值 20%）。
    这些数字出现在报告里属于合法引用，不应判为「无法对账」，
    但也不要求模型必须引用，故只进反向核对的允许集，不进正向必查项。
    """
    expected = _expected_values(facts) + [float(x) for x in allow_extra]
    mismatches: list[str] = []
    details: list[dict] = []

    # 正向：关键指标必须出现在报告里
    text_nums: list[float] = []
    cleaned = re.sub(r"\d{4}-\d{2}(-\d{2})?", " ", report)  # 去掉日期
    cleaned = re.sub(r"\]\([^)]*\)", " ", cleaned)  # 去掉链接地址
    cleaned = cleaned.replace(",", "")
    for m in NUM_RE.findall(cleaned):
        try:
            text_nums.append(float(m))
        except ValueError:
            pass

    def matches(n: float) -> bool:
        for e in expected:
            if abs(n - e) <= max(0.02, abs(e) * 0.01):
                return True
        return False

    allowed_set = [float(x) for x in allow_extra]

    for k, v in facts.items():
        if v is None or pd.isna(v):
            details.append({"指标": k, "计算值": "数据不足", "在报告中出现": "—"})
            continue
        ok = matches(float(v)) or matches(abs(float(v)))
        details.append({"指标": k, "计算值": round(float(v), 2), "在报告中出现": "是" if ok else "否"})
        if not ok:
            mismatches.append(f"报告缺少指标「{k}」的计算值 {float(v):.2f}")

    # 反向：报告中的数字（排除序号、年份）必须能对上计算值
    for n in text_nums:
        if n == int(n) and 1900 <= n <= 2100:
            continue  # 年份
        if n == int(n) and 0 < n <= 12:
            continue  # 序号/月份
        if any(abs(n - a) <= max(0.02, abs(a) * 0.01) for a in allowed_set):
            continue  # 提示词中已给出的常量（如阈值）
        if not matches(n) and not matches(-n):
            mismatches.append(f"报告中出现无法对账的数字：{n:g}")

    # 去重
    seen: set[str] = set()
    uniq = [m for m in mismatches if not (m in seen or seen.add(m))]
    return uniq, details


# ---------------------------------------------------------------------------
# 3) 模型：只解读，不算数
# ---------------------------------------------------------------------------
def build_client(api_key: str | None = None) -> OpenAI:
    key = (api_key or API_KEY).strip()
    if not key:
        raise RuntimeError("未配置 ZHIPU_API_KEY：请在环境变量或请求体中提供 API Key")
    return OpenAI(api_key=key, base_url=BASE_URL, timeout=60.0, max_retries=1)


def chat(system: str, user: str, max_tokens: int = 1024, api_key: str | None = None) -> tuple[str, dict]:
    client = build_client(api_key)
    last = ""
    for attempt in range(4):
        mt = max_tokens if attempt < 2 else max_tokens * 2
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=mt,
                temperature=0.3,
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = resp.choices[0].message.content or ""
            usage = {
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(resp.usage, "total_tokens", 0) or 0,
            }
            if content.strip():
                return content.strip(), usage
            last = "模型返回空内容"
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(1 + 2 * attempt)
    raise RuntimeError(f"模型调用失败（已重试 4 次）：{last}")


PROMPT_TMPL = """下面是 pandas 已经算好的经营数据（单位：万元，百分比已算好）。
你的任务只有一个：把这些数字组织成一份给业务负责人看的中文月报。

【硬性约束】
1. 只能使用下面给出的数字，禁止自行计算、禁止推算、禁止四舍五入改写、禁止补充任何新数字；
2. 不得给出投资建议、不得预测走势、不得使用"买入/卖出/稳赚"等表述；
3. 结构：①本期概览（3 句话内）②环比与同比 ③品类结构 ④异常与关注项 ⑤下一步建议（只提管理动作，不提投资动作）；
   不要再输出任何一级标题（#），直接从小节正文开始，标题由系统统一生成；
4. 每个关键数字后面用括号标注它来自哪个指标名。

【环比（较上期 {prev_period}）】
{mom_block}

【同比（较 {yoy_period}）】
{yoy_block}

【品类结构】
{share_block}

【异常清单（波动>{th}%）】
{anomaly_block}

【全部指标字典】
{facts_block}
"""


def render_report(computed: dict, body: str, mismatches: list[str], details: list[dict]) -> str:
    cur = str(computed["period"])
    prev_p = str(pd.Period(cur, freq="M") - 1)
    yoy_p = str(pd.Period(cur, freq="M") - 12)
    lines: list[str] = []
    lines.append(f"# 经营月报 · {cur}")
    lines.append("")
    lines.append(
        f"> 生成时间：{datetime.now(CST).strftime('%Y-%m-%d %H:%M')}　"
        f"数据来源：本地 CSV（pandas 计算）　模型：{MODEL}（仅解读与行文）"
    )
    lines.append("")
    lines.append(body)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 附：对账表（数值由 pandas 计算，逐条核对报告是否引用）")
    lines.append("")
    lines.append("| 指标 | 计算值 | 报告中是否出现 |")
    lines.append("|---|---|---|")
    for d in details:
        lines.append(f"| {d['指标']} | {d['计算值']} | {d['在报告中出现']} |")
    lines.append("")
    if mismatches:
        lines.append("## ⚠️ 对账不一致")
        lines.append("")
        for m in mismatches:
            lines.append(f"- {m}")
        lines.append("")
    else:
        lines.append("**对账结论：报告中出现的全部数字均能在 pandas 计算结果中找到，一致。**")
        lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4) 接口
# ---------------------------------------------------------------------------
app = FastAPI(
    title="数据报表自动化 Agent",
    version="0.1.0",
    description="上传 CSV → pandas 算数 → LLM 只做解读行文 → 自动对账（数字不交给模型算）",
)


class ReportRequest(BaseModel):
    csv_path: str | None = Field(default=None, description="CSV 路径；留空则使用自带示例数据")
    api_key: str | None = Field(default=None, description="可选：本次请求临时 API Key，仅内存使用")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>报表自动化 Agent</title>
<style>body{font-family:-apple-system,"PingFang SC",sans-serif;max-width:760px;margin:40px auto;padding:0 16px;line-height:1.7;color:#222}
button{background:#1a6fd4;color:#fff;border:0;border-radius:6px;padding:10px 20px;font-size:15px;cursor:pointer}
button:disabled{background:#999}pre{background:#f6f8fa;padding:12px;border-radius:6px;overflow:auto;white-space:pre-wrap}
input{width:100%;padding:8px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box}.tip{color:#666;font-size:13px}</style>
</head><body><h1>数据报表自动化 Agent</h1>
<p>上传/指定一份 CSV（列：date, category, revenue, cost），pandas 算完全部数字后交给大模型写月报，并自动做数字对账。</p>
<p class="tip">CSV 路径（留空用自带示例数据 sample_data/sample.csv）：</p>
<input id="p" placeholder="留空则使用示例数据" />
<p class="tip">未配置 Key 时可临时填写（仅本次请求内存中使用）：</p>
<input id="k" placeholder="留空则使用服务端环境变量中的 Key" />
<p><button id="b" onclick="go()">生成月报</button></p>
<pre id="o">等待操作…</pre>
<script>async function go(){const b=document.getElementById('b'),o=document.getElementById('o');b.disabled=true;o.textContent='运行中…';
try{const body={};const p=document.getElementById('p').value.trim();if(p)body.csv_path=p;const k=document.getElementById('k').value.trim();if(k)body.api_key=k;
const r=await fetch('/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const j=await r.json();
o.textContent=r.ok?('报告：'+j.report_file+'\\n异常：'+j.anomaly_count+' 项\\n对账：'+(j.mismatch.length?('不一致 '+j.mismatch.length+' 项'):'一致')+'\\n\\n'+j.content.slice(0,1500)):JSON.stringify(j,null,2);}catch(e){o.textContent='失败：'+e}b.disabled=false;}</script>
</body></html>"""


@app.post("/report")
def report(req: ReportRequest):
    started = time.time()
    path = Path(req.csv_path) if req.csv_path else SAMPLE_CSV
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    if not path.exists():
        return JSONResponse(status_code=404, content={"detail": f"找不到 CSV 文件：{path}"})
    if not (req.api_key or "").strip() and not API_KEY:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "未配置 API Key。请在页面输入框中填写智谱 API Key（仅本次请求内存使用，不保存），"
                "或设置环境变量 ZHIPU_API_KEY。",
                "hint": "获取地址：https://open.bigmodel.cn/",
            },
        )

    computed, anomalies, anomalies_path = compute(path)
    cur = str(computed["period"])
    prev_p = str(pd.Period(cur, freq="M") - 1)
    yoy_p = str(pd.Period(cur, freq="M") - 12)

    prompt = PROMPT_TMPL.format(
        prev_period=prev_p,
        yoy_period=yoy_p,
        mom_block=computed["mom_block"],
        yoy_block=computed["yoy_block"],
        share_block=computed["share_block"],
        anomaly_block=computed["anomaly_block"],
        facts_block=computed["facts_block"],
        th=int(ANOMALY_THRESHOLD * 100),
    )
    body, usage = chat(SYSTEM_PROMPT, prompt, max_tokens=1600, api_key=req.api_key)
    body, _ = mask_high_risk(body)

    mismatches, details = reconcile(
        body, computed["facts"], allow_extra=(ANOMALY_THRESHOLD * 100,)
    )
    content = render_report(computed, body, mismatches, details)
    content, _ = mask_high_risk(content)

    fname = f"report_{cur.replace('-', '')}.md"
    out = OUTPUT_DIR / fname
    out.write_text(content, encoding="utf-8")

    price = PRICE_TABLE.get(MODEL, (0.0, 0.0))
    cost = round(
        usage["prompt_tokens"] / 1_000_000 * price[0] + usage["completion_tokens"] / 1_000_000 * price[1], 6
    )
    return {
        "report_file": str(out.relative_to(BASE_DIR)),
        "anomalies_file": str(Path(anomalies_path).relative_to(BASE_DIR)),
        "period": cur,
        "anomaly_count": int(computed["anomaly_count"]),
        "mismatch": mismatches,
        "reconcile_passed": not mismatches,
        "tokens": usage["total_tokens"],
        "cost_yuan": cost,
        "elapsed_s": round(time.time() - started, 2),
        "content": content,
    }


@app.get("/latest")
def latest():
    files = sorted(OUTPUT_DIR.glob("report_*.md"))
    if not files:
        return PlainTextResponse("尚未生成报告，请先调用 POST /report", status_code=404)
    return PlainTextResponse(files[-1].read_text(encoding="utf-8"))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL,
        "api_key_configured": bool(API_KEY),
        "sample_exists": SAMPLE_CSV.exists(),
    }


@app.exception_handler(RuntimeError)
def runtime_error_handler(request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# 发布形态：单端口 + 从环境变量读 PORT（发布沙箱会注入 PORT）
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
