# services/gateway —— 模型网关

自写外壳 + LiteLLM 库：对外完全是 OpenAI 格式；模型注册表 `models.yaml` 决定接哪些模型、能力和失败切换顺序；
兼容层 `app/compat/` 抹平各家差异（架构设计 §2.3.4 的 14 类）。端口 **8100**。

## 本地运行

```bash
cd services/gateway
uv sync
uv run uvicorn app.main:app --reload --port 8100
uv run pytest                      # 单元测试 + 接口测试（离线），契约测试默认 skip
uv run ruff check . && uv run ruff format --check .
```

环境变量（与根目录 `.env.example` 一致）：`HUNYUAN_API_BASE/KEY`、`DEEPSEEK_API_BASE/KEY`、`DASHSCOPE_API_BASE/KEY`、
`GATEWAY_INTERNAL_KEY`、`GATEWAY_MODELS_FILE`、`GATEWAY_TIMEOUT_SECONDS`。本地开发会自动读取仓库根目录的 `.env`。
没有配 Key 的模型标记为 `unavailable`，服务照常启动，分组里自动跳过。

## 接口

| 接口 | 鉴权 | 说明 |
|---|---|---|
| `POST /v1/chat/completions` | Bearer | `model` 填别名或分组名；支持 `stream`、`tools`、`tool_choice`、`response_format` |
| `POST /v1/embeddings` | Bearer | `model` 填 `embed` |
| `GET /v1/models` | Bearer | OpenAI `list` 结构，扩展 `type`(model/group)、`capabilities`、`available`、`groups`、`members` |
| `GET /health` | 无 | 网关状态 + 每个模型可用性和最近一次调用结果 |

- 鉴权：`Authorization: Bearer <GATEWAY_INTERNAL_KEY>`，失败返回 401（OpenAI 错误结构，`gateway_code: 40101`）。
- `X-Request-ID` 透传，没有就生成，并放回响应头。
- 错误一律为 `{"error": {"message", "type", "param", "code", "gateway_code"}}`，错误码见开发规范 §8.2。
- 流式：SSE `data: {chat.completion.chunk}`，最后一片带 `finish_reason` 和 `usage`（估算时 `usage.estimated: true`），
  以 `data: [DONE]` 结束；上游中途断开时发送 `data: {"error": {...}}` 且不再切换模型。
- 响应头 `X-Request-ID`；响应体 `model` 字段是**实际使用的模型别名**（请求分组时可据此知道切到了哪个模型）。

## 代码结构

```
models.yaml            注册表（新增模型只改这里）
app/main.py            HTTP 接口、鉴权、request_id、错误处理
app/registry.py        读取注册表、展开 ${ENV}、能力查询、分组解析（#12）
app/router.py          分组失败切换：只在首字节之前切换（#14）、伪流式（#11）
app/backend.py         litellm.Router 封装（协议转换、同模型重试）；测试里替换为 Fake
app/compat/request.py  请求规范化 #1–#4
app/compat/response.py 响应规范化 #5 #6 #8 #9
app/compat/stream.py   流式规范化 #7 #8 #9 #10，伪流式 #11
app/compat/errors.py   错误统一 #13
app/logging.py         结构化 JSON 日志
tests/unit             兼容层纯函数 + 路由 + 接口测试（离线）
tests/fixtures         各家返回样本；synthetic/ 是手写模拟样本，<别名>/ 是契约测试录制的真实样本
tests/contract         10 个契约用例（RUN_CONTRACT=1 时访问真实模型）
scripts/compat_matrix.py  生成 docs/模型兼容矩阵.md
```

## 接入新模型（4 步，不改代码）

1. **加注册表**：在 `models.yaml` 的 `models` 下加一条：`alias`、`link`（`openai_compat` 或 `native`）、`model`
   （以官方文档为准）、`api_base: ${XXX_API_BASE}`、`api_key: ${XXX_API_KEY}`、`capabilities`；
   在根目录 `.env.example` 补上对应环境变量名，在自己的 `.env` 填真实值（不要提交）。
2. **跑契约测试**：`RUN_CONTRACT=1 uv run pytest tests/contract -k <别名>`，共 10 个用例
   （普通对话、流式、单工具、并行工具、流式工具、工具结果第二轮、JSON 输出、上下文超长、错误 Key、分组失败切换）。
3. **录制样本 + 更新矩阵**：契约测试会把上游原始返回录到 `tests/fixtures/<别名>/`；
   再运行 `uv run python scripts/compat_matrix.py` 更新 `docs/模型兼容矩阵.md`。
4. **按结果修正能力并加入分组**：不通过的能力在 `models.yaml` 里改成 `false`（兼容层自动降级，例如
   `stream_tools: false` → 伪流式，`tool_choice_required: false` → `auto` + 提示词），然后把模型加进合适的分组
   （`chat-agent` 只放 `tools: true` 的模型）。
