package com.example.investintel.service;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/**
 * 抓取 RSS → 清洗去重 → 模型摘要打标 → 渲染带免责声明的简报 → 落盘 output/。
 * 数值与事实只来自抓取原文；模型只做摘要与打标，不做任何投资判断。
 */
@Service
public class BriefService {

    public record Source(String name, String url) {}
    public record Article(String source, String title, String link, String published, String summary) {}

    private static final ZoneId CST = ZoneId.of("Asia/Shanghai");
    private static final List<Source> SOURCES = List.of(
            new Source("中新网·财经", "https://www.chinanews.com.cn/rss/finance.xml"),
            new Source("中新网·要闻", "https://www.chinanews.com.cn/rss/importnews.xml"),
            new Source("中新网·滚动", "https://www.chinanews.com.cn/rss/scroll-news.xml"));

    private static final Pattern ITEM = Pattern.compile("<item[\\s>].*?</item>", Pattern.DOTALL);
    private static final Pattern TITLE = Pattern.compile("<title[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?</title>", Pattern.DOTALL);
    private static final Pattern LINK = Pattern.compile("<link[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?</link>", Pattern.DOTALL);
    private static final Pattern DESC = Pattern.compile("<description[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?</description>", Pattern.DOTALL);
    private static final Pattern JSON_OBJ = Pattern.compile("\\{[^{}]*}", Pattern.DOTALL);

    private final ChatClient chatClient;
    private final DisclaimerService disclaimer;
    private final TraceService trace;
    private final int timeoutSeconds;
    private final int maxArticles;
    private final Path outputDir;
    private final HttpClient http;

    public BriefService(ChatClient chatClient, DisclaimerService disclaimer, TraceService trace,
                        @Value("${app.fetch.timeout-seconds:8}") int timeoutSeconds,
                        @Value("${app.fetch.max-articles:4}") int maxArticles,
                        @Value("${app.storage.output-dir:output}") String outputDir) {
        this.chatClient = chatClient;
        this.disclaimer = disclaimer;
        this.trace = trace;
        this.timeoutSeconds = timeoutSeconds;
        this.maxArticles = maxArticles;
        this.outputDir = Paths.get(outputDir);
        this.http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(timeoutSeconds)).build();
    }

    public Map<String, Object> run() {
        long start = System.currentTimeMillis();
        List<String> errors = new ArrayList<>();

        List<Article> articles = fetch(errors);
        boolean fallback = false;
        if (articles.size() < 3) {
            articles = fallbackArticles();
            fallback = true;
            errors.add("信源不足 3 条，已切换内置示例数据（非真实新闻）");
        }
        if (articles.size() > maxArticles) {
            articles = articles.subList(0, maxArticles);
        }

        List<Map<String, String>> items = new ArrayList<>();
        for (Article a : articles) {
            String tag = "中性";
            String summary;
            try {
                String raw = chatClient.prompt().user(summarizePrompt(a)).call().content();
                Matcher m = JSON_OBJ.matcher(raw == null ? "" : raw);
                if (m.find()) {
                    tag = extractField(m.group(), "tag", "中性");
                    summary = extractField(m.group(), "summary", "");
                } else {
                    summary = raw == null ? "" : raw.strip();
                }
                if (!"利好".equals(tag) && !"风险".equals(tag)) {
                    tag = "中性";
                }
                if (summary == null || summary.isBlank()) {
                    summary = ruleBased(a);
                }
            } catch (Exception e) {
                errors.add("摘要降级为规则摘录：" + e.getMessage());
                summary = ruleBased(a);
            }
            Map<String, String> it = new LinkedHashMap<>();
            it.put("source", a.source());
            it.put("title", a.title());
            it.put("link", a.link());
            it.put("published", a.published());
            it.put("tag", tag);
            it.put("summary", truncate(summary.replace("\n", " ").strip(), 80));
            items.add(it);
        }

        // 排序：利好 → 中性 → 风险
        items.sort(Comparator.comparingInt(it -> tagOrder(it.get("tag"))));

        String content = renderBrief(items, countOkSources(errors), fallback, errors);
        String fileName = "brief_" + LocalDate.now(CST).format(DateTimeFormatter.ofPattern("yyyyMMdd")) + ".md";
        Path outPath = outputDir.resolve(fileName);
        try {
            Files.createDirectories(outputDir.toAbsolutePath());
            Files.writeString(outPath, content, StandardCharsets.UTF_8);
        } catch (Exception e) {
            errors.add("简报落盘失败：" + e.getMessage());
        }

        long elapsed = System.currentTimeMillis() - start;
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("ts", OffsetDateTime.now(CST).toString());
        row.put("endpoint", "/run");
        row.put("sources", countOkSources(errors));
        row.put("articles", items.size());
        row.put("elapsed_ms", elapsed);
        row.put("file", fileName);
        row.put("fallback", fallback);
        row.put("errors", errors.size() > 5 ? errors.subList(0, 5) : errors);
        trace.append(row);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("file", outPath.toString());
        result.put("articles", items.size());
        result.put("sources", countOkSources(errors));
        result.put("elapsed_ms", elapsed);
        result.put("fallback", fallback);
        result.put("errors", errors);
        result.put("content", content);
        return result;
    }

    private String summarizePrompt(Article a) {
        return "请基于下面这条资讯做整理，严格只输出一行 JSON，不要任何解释、不要 Markdown 代码块：\n"
                + "{\"tag\": \"利好|中性|风险\", \"summary\": \"80 字以内的客观摘要，只陈述事实\"}\n"
                + "打标规则：只有原文明确表述正面影响才标【利好】；明确表述负面影响、违规、下滑、警示才标【风险】；"
                + "无法判断或中性事实一律标【中性】。不确定时不要标利好。\n\n"
                + "标题：" + a.title() + "\n来源：" + a.source() + "\n原文摘要：" + truncate(a.summary(), 300) + "\n";
    }

    private List<Article> fetch(List<String> errors) {
        List<Article> articles = new ArrayList<>();
        for (Source src : SOURCES) {
            try {
                HttpRequest req = HttpRequest.newBuilder(URI.create(src.url()))
                        .timeout(Duration.ofSeconds(timeoutSeconds))
                        .header("User-Agent", "Mozilla/5.0 (invest-intel-agent/1.0)")
                        .GET().build();
                HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
                if (resp.statusCode() != 200) {
                    errors.add(src.name() + "：HTTP " + resp.statusCode());
                    continue;
                }
                List<Article> parsed = parseFeed(src, resp.body(), errors);
                if (parsed.isEmpty()) {
                    errors.add(src.name() + "：无可用条目");
                }
                articles.addAll(parsed);
            } catch (Exception e) {
                errors.add(src.name() + "：" + e.getClass().getSimpleName());
            }
        }
        // 清洗去重（按标题前 60 字）
        List<Article> cleaned = new ArrayList<>();
        java.util.Set<String> seen = new java.util.HashSet<>();
        for (Article a : articles) {
            if (a.title() == null || a.title().isBlank()) {
                continue;
            }
            String key = truncate(a.title(), 60);
            if (seen.add(key)) {
                cleaned.add(a);
            }
        }
        return cleaned;
    }

    private List<Article> parseFeed(Source src, String xml, List<String> errors) {
        List<Article> list = new ArrayList<>();
        Matcher itemMatcher = ITEM.matcher(xml);
        int count = 0;
        while (itemMatcher.find() && count < 5) {
            String item = itemMatcher.group();
            String title = stripTags(first(TITLE, item));
            String link = first(LINK, item);
            String desc = stripTags(first(DESC, item));
            if (title.isBlank()) {
                continue;
            }
            list.add(new Article(src.name(), title, link == null ? "" : link.strip(),
                    LocalDateTime.now(CST).format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")),
                    desc == null ? "" : truncate(desc.strip(), 400)));
            count++;
        }
        return list;
    }

    private String renderBrief(List<Map<String, String>> items, int sourcesOk, boolean fallback, List<String> errors) {
        String today = LocalDate.now(CST).format(DateTimeFormatter.ofPattern("yyyy-MM-dd"));
        StringBuilder sb = new StringBuilder();
        sb.append("# 投研情报简报 · ").append(today).append("\n\n");
        sb.append("> 生成时间：").append(LocalDateTime.now(CST).format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")))
                .append("（北京时间）　信源：").append(sourcesOk).append(" 个　条目：").append(items.size()).append(" 条");
        if (fallback) {
            sb.append("（本次使用内置示例数据，非真实新闻）");
        }
        sb.append("\n\n## 一、今日要点\n");
        for (Map<String, String> it : items) {
            sb.append("- 【").append(it.get("tag")).append("】")
                    .append(sanitizeAbsoluteWording(it.get("title"))).append("\n");
        }
        sb.append("\n## 二、分条摘要\n");
        int idx = 1;
        for (Map<String, String> it : items) {
            sb.append("### ").append(idx++).append(". 【").append(it.get("tag")).append("】")
                    .append(sanitizeAbsoluteWording(it.get("title"))).append("\n\n");
            sb.append(it.get("summary") == null || it.get("summary").isBlank()
                            ? "（模型未返回摘要）"
                            : sanitizeAbsoluteWording(it.get("summary")))
                    .append("\n\n");
            sb.append("- 来源：").append(it.get("source")).append("\n");
            if (it.get("link") != null && !it.get("link").isBlank()) {
                sb.append("- 原文：").append(it.get("link")).append("\n");
            }
            sb.append("\n");
        }
        sb.append("## 三、风险与非正面条目\n");
        boolean anyRisky = false;
        for (Map<String, String> it : items) {
            if ("风险".equals(it.get("tag"))) {
                sb.append("- ").append(sanitizeAbsoluteWording(it.get("title")))
                        .append("：").append(sanitizeAbsoluteWording(it.get("summary"))).append("\n");
                anyRisky = true;
            }
        }
        if (!anyRisky) {
            sb.append("- 本次未标记风险条目。\n");
        }
        if (!errors.isEmpty()) {
            sb.append("\n## 四、运行提示\n");
            for (String e : errors) {
                sb.append("- ").append(e).append("\n");
            }
        }
        sb.append("\n---\n\n").append(disclaimer.text()).append("\n");
        return sb.toString();
    }

    private List<Article> fallbackArticles() {
        String src = "内置示例数据（离线兜底）";
        return new ArrayList<>(List.of(
                new Article(src, "示例条目一：公开市场操作与流动性投放口径调整", "https://example.com/demo-1", "",
                        "【示例数据，非真实新闻】用于演示离线环境下的完整链路：抓取→清洗→摘要→成稿。"),
                new Article(src, "示例条目二：某行业季度产能利用率披露口径变更", "https://example.com/demo-2", "",
                        "【示例数据，非真实新闻】用于验证摘要与标签（利好/中性/风险）链路可用。"),
                new Article(src, "示例条目三：跨境结算便利化试点范围扩大", "https://example.com/demo-3", "",
                        "【示例数据，非真实新闻】用于验证简报落盘、trace 记录与合规过滤。")));
    }

    private int countOkSources(List<String> errors) {
        int ok = SOURCES.size();
        for (Source s : SOURCES) {
            for (String e : errors) {
                if (e.startsWith(s.name())) {
                    ok--;
                    break;
                }
            }
        }
        return Math.max(ok, 0);
    }

    private static int tagOrder(String tag) {
        if ("利好".equals(tag)) return 0;
        if ("风险".equals(tag)) return 2;
        return 1;
    }

    private static String ruleBased(Article a) {
        String text = a.summary() == null ? "" : a.summary().replaceAll("【[^】]*】", "").strip();
        String snippet = text.split("[。！？\\n]")[0].strip();
        if (snippet.isEmpty()) {
            snippet = a.title();
        }
        return snippet;
    }

    private static String extractField(String json, String field, String dflt) {
        Matcher m = Pattern.compile("\"" + field + "\"\\s*:\\s*\"(.*?)\"", Pattern.DOTALL).matcher(json);
        return m.find() ? m.group(1).strip() : dflt;
    }

    private static String first(Pattern p, String s) {
        Matcher m = p.matcher(s);
        return m.find() ? m.group(1) : null;
    }

    private static String stripTags(String s) {
        return s == null ? "" : s.replaceAll("<[^>]+>", "").replace("&nbsp;", " ").trim();
    }

    private static String truncate(String s, int max) {
        if (s == null) {
            return "";
        }
        return s.length() <= max ? s : s.substring(0, max) + "…";
    }

    /**
     * 绝对化措辞净化（代码层兜底，不依赖模型自觉）。
     *
     * <p>模型在转述外部新闻时可能原样照搬「全球第一」这类绝对化表述。
     * 系统提示词已约束，但金融场景不能只靠提示词——发布到闲鱼/小红书
     * 的内容含这类词会被限流甚至封号，故在落盘前强制改写为中性表述。
     * 仅处理措辞，不改变事实指向（"位居全球第一" → "位居全球前列"）。
     */
    private static String sanitizeAbsoluteWording(String s) {
        if (s == null || s.isEmpty()) {
            return s;
        }
        String[][] rules = {
                {"位居全球第一", "位居全球前列"},
                {"全球第一", "全球前列"},
                {"全球首位", "全球前列"},
                {"世界第一", "世界前列"},
                {"全国第一", "全国前列"},
                {"行业第一", "行业前列"},
                {"份额最高", "份额居前"},
                {"规模最大", "规模居前"},
                {"全球领先", "全球具备竞争力"},
                {"最好", "较好"},
                {"最佳", "较优"},
                {"最优", "较优"},
                {"独家首创", "较为少见"},
        };
        String out = s;
        for (String[] r : rules) {
            out = out.replace(r[0], r[1]);
        }
        return out;
    }
}
