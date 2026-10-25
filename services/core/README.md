# SalesPilot core（业务后端）

FastAPI + SQLAlchemy 2 + LangGraph。负责 CRM 增删改查、业务规则、数据权限、Agent、行业包和 RAG。
规范见仓库根目录 `AGENTS.md`、`docs/开发规范.md`、`docs/架构设计.md`。

> **所有产品价格、成本均为模拟数据**（`app/packs/*/catalog.json`），仅用于课程演示。

## 快速开始

```bash
cd services/core
uv sync                                  # Python 3.12（uv python install 3.12）
docker compose up -d db                  # 在仓库根目录执行，启动 Postgres + pgvector
uv run alembic upgrade head              # 建表（含 CREATE EXTENSION vector）
uv run python -m seed                    # 演示数据；--with-kb 同时入库知识库（需要网关）
uv run uvicorn app.main:app --reload --port 8000
```

- 数据库连不上时服务仍能启动：`/health` 返回 `status=degraded, db=false`，Agent 会话退回内存 checkpointer。
- 接口文档：<http://localhost:8000/docs>
- 配置只从环境变量读取（变量名与根目录 `.env.example` 一致），本地开发会依次读取 `../../.env` 和 `./.env`。

## 测试与检查

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest                            # 无数据库时 tests/api/test_customers.py 自动 skip
```

测试不依赖外网和真实 Key：Agent 用例用假模型（`GenericFakeChatModel`）、内存 checkpointer 和假的报价 service。

## 目录

```
app/
  main.py                 FastAPI 入口：路由、/health、X-Request-ID、全局异常处理
  common/                 config · db · errors(§8.2) · response(统一响应) · auth(JWT) · scope(数据范围) · request_id
  llm/client.py           唯一的大模型入口（ChatOpenAI → 网关；embeddings；/models）
  crm/models|schemas|services|routers
                          customers 为参考实现；其他模块路由在 routers/stubs.py，返回 501
  rules/                  rules.yaml + 纯函数：check_margin / calc_commission / check_expense_policy / check_discount
  packs/                  base.py(Configurator) · registry.py · llm_deploy/（显存估算 + 三档 BOM）· it_office/（最小版）
  agent/                  state · graph · nodes/ · tools/ · prompts/ · sse · service · checkpoint · router
  rag/                    chunking（800/120，中文分隔符，哈希去重）· ingest · retriever（scope 过滤，阈值 0.5）
migrations/               Alembic（0001 含 CREATE EXTENSION vector 与 HNSW 索引）
seed/                     python -m seed；seed/knowledge/company/ 为公司制度文档
tests/unit  tests/api
```

## 接口一览

| 接口 | 状态 |
|---|---|
| `POST /api/auth/mock-login`、`GET /api/me` | 已实现（演示身份为固定 UUID，与 seed 一致，不查库） |
| `GET/POST /api/customers`、`GET /api/customers/{id}` | 已实现（参考实现，按数据范围过滤） |
| `POST /api/agent/chat`、`POST /api/agent/resume` | 已实现（SSE，事件见开发规范 §8.3） |
| `GET /api/packs`、`POST /api/commissions/estimate`、`POST /api/expenses/precheck` | 已实现（纯规则） |
| 商机、报价、合同、报销、审批、产品线映射 | 占位，返回 501 `{"code":50101}`，TODO 见 `app/crm/routers/stubs.py` |

## Agent 状态图

```
START → router ─┬─ chitchat   → respond
                ├─ crm_action → tool_agent → respond
                └─ solution   → parse_requirement ─┬─ 缺信息 → ask_user → END
                                                   └─ configure → price → check_margin
                                                        ├─ 不达标且 retry < 2 → configure（node.retry）
                                                        ├─ 不达标且 retry = 2 → respond
                                                        └─ 达标 → confirm（interrupt）→ save_quote → respond
```

现阶段的占位：router 用关键词分类、parse_requirement 用行业包的规则抽取、tool_agent 用规则选工具；
respond 在网关可用时用大模型流式解释工具结果，不可用时用模板。数字一律来自规则代码。

## 显存估算（大模型部署包）

`权重 = 参数量 × 字节数`；`KV Cache = 2 × 层数 × KV 维度 × 上下文 × 并发 × 字节数`；`总量 = (权重 + KV) × 1.2`。
KV 维度 = KV 头数 × 每头维度（GQA 模型按它计算，规范原文写的「隐藏维度」会高估约 5 倍）。参数表在 `app/packs/llm_deploy/knowledge/models.json`。
