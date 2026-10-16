# v1-invest-intel · 投研情报 Agent（Java 私有化版）

> 双轨策略的 v1.0 形态：给对「数据不出域」有要求的客户，可私有部署的 Java 服务。
> 技术栈：Spring Boot 4.1.1 + Spring AI 2.0.1 + JDK 17，走 OpenAI 兼容协议接智谱 GLM。

## 一、启动命令

### 方式 1：本地源码运行（需 JDK 17 + Maven）
```bash
export SPRING_AI_OPENAI_API_KEY="你的Key"
export SPRING_AI_OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
export SPRING_AI_OPENAI_MODEL="glm-4.5-flash"
mvn -DskipTests spring-boot:run
```
> 实测：`Started InvestIntelApplication`，Tomcat 监听 8080，启动约 2 秒。

### 方式 2：Docker
```bash
docker build -t v1-invest-intel:1.0.0 .
docker run -d -p 8080:8080 -e SPRING_AI_OPENAI_API_KEY="你的Key" v1-invest-intel:1.0.0
```

## 二、配置项

| 环境变量 | 含义 | 默认值 |
|----------|------|--------|
| SPRING_AI_OPENAI_API_KEY | 模型接口密钥（必填，无默认、不硬编码） | 无 |
| SPRING_AI_OPENAI_BASE_URL | 模型服务地址 | https://open.bigmodel.cn/api/paas/v4 |
| SPRING_AI_OPENAI_MODEL | 模型名 | glm-4.5-flash |
| SERVER_PORT | 服务端口 | 8080 |

> ⚠️ 密钥只从环境变量读取，代码与镜像内均不落密钥。

## 三、接口清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/chat?msg=你好&session=default` | 返回模型回复（末尾强制附免责声明，带会话记忆） |
| POST | `/run` | 触发「抓取→清洗→摘要→成简报」，返回简报 JSON + 落盘 |
| GET | `/latest` | 返回最近一次生成的简报正文 |
| GET | `/health` | 健康检查 |

## 四、实测记录（2026-10-16）

- `curl "http://127.0.0.1:8080/chat?msg=你好"` → 返回非空，末尾含「仅供参考，不构成投资建议」✅
- `curl -X POST "http://127.0.0.1:8080/run"` → HTTP 200，耗时约 37 秒，抓取 3 个信源、4 条真实资讯，简报落盘 `output/brief_YYYYMMDD.md` ✅
- 单条摘要遇 429 限流时，自动降级为「规则摘录」，保证简报始终有输出 ✅
- 每次调用写入 `logs/trace.jsonl`（时间/接口/耗时/是否含免责声明）✅

## 五、私有化部署说明

- 仅依赖 JDK 17 运行环境（或 Docker），无数据库，存储只用本地文件；
- 换模型：改 `SPRING_AI_OPENAI_MODEL`；换服务商：改 `SPRING_AI_OPENAI_BASE_URL`；
- 换信源：编辑 `BriefService` 中的 SOURCES 列表后重新构建；
- 交付文档包见 `../docs/delivery/`（部署文档 / 运维手册 / 培训一页纸 / 验收清单）。

## 六、已知限制

- 信源当前为公开 RSS（中新网 3 源），抓取受网络与信源可用性影响，失败时回退内置示例数据；
- 免费档模型存在限流，高峰时段可能出现单条降级，生产建议使用付费档；
- 会话记忆为进程内内存实现，服务重启后清空；
- 未内置鉴权，私有化部署时请放在内网或网关后。
