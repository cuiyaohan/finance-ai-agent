# 作品集总架构

> 金融 + 科技垂直的「流程重写者」作品集。两条轨道、两个已验证 Demo、一道共用合规护栏。

## 一、双轨策略

| 轨道 | 用途 | 技术栈 | 能否一键发布链接 |
|---|---|---|---|
| **v0.1 验证体** | 验证客户要不要、做演示、做获客素材 | Python + FastAPI | ✅ 能，用 WorkBuddy「发布为应用」 |
| **v1.0 交付体** | 私有化交付、建立壁垒、收定制费 | Java 17 + Spring Boot + Spring AI | ❌ 不能，只用 GitHub + 录屏 + 截图对外 |

## 二、总架构图（Mermaid）

```mermaid
flowchart TB
    subgraph 信源层
        S1[RSS 财经信源 ×3]
        S2[业务 CSV 数据]
    end

    subgraph 计算/整理层
        C1[抓取 → 清洗 → 去重 → 新鲜度过滤]
        C2[pandas 算数<br/>总额/环比/同比/占比/异常]
    end

    subgraph 模型层
        M1[智谱 GLM · 摘要打标]
        M2[智谱 GLM · 仅解读行文]
    end

    subgraph 护栏层
        G[共用合规护栏<br/>高危词打码 + 免责声明 + 对账]
    end

    subgraph 产物层
        P1[output/brief_YYYYMMDD.md]
        P2[output/report_YYYYMM.md + anomalies.csv]
        T[trace.jsonl 成本日志 /stats]
    end

    subgraph 分发层
        D1[发布为应用 → 在线链接]
        D2[GitHub + 录屏 + 截图]
    end

    S1 --> C1 --> M1 --> G --> P1
    S2 --> C2 --> M2 --> G --> P2
    M1 --> T
    M2 --> T
    P1 --> D1
    P2 --> D1
    P1 --> D2
    P2 --> D2
```

## 三、设计要点

1. **模型只做「信息整理 / 行文」，所有数字与判断来自上游确定性模块**（抓取、pandas）。模型被系统提示词约束为「只陈述事实、不预测、不给建议」。
2. **合规护栏共用**：高危词扫描、免责声明、对账校验统一在 `agent-demos/check_compliance.sh` 与 `_shared/` 下维护，两 Demo 复用。
3. **可观测**：每次运行写 `trace.jsonl`，`/stats` 汇总 Token、耗时、成本，方便对客户讲「多少钱一次」。
4. **发布形态**：v0.1 走「发布为应用」拿在线链接直接获客；v1.0 走 GitHub + 录屏 + 截图做私有化交付背书。
