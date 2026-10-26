# AGENTS.md —— 给 AI 编程助手（XBuddy / Claude Code 等）的项目规范

> 每次开始编码前先读本文件。详细规范在 `docs/开发规范.md`，架构在 `docs/架构设计.md` 和 `docs/架构图.html`，界面以 `prototype/index.html` 为准。
> 本文件与 docs 冲突时，以 docs 为准，并在 ai-log 里记下冲突。

## 1. 项目是什么
SalesPilot：面向 ToB 销售的 AI CRM。销售用自然语言完成记跟进、推进商机、出方案报价、算提成、报销；Agent 通过工具调用真实读写业务数据；行业知识以「行业包」插件提供。

## 2. 仓库结构（单仓多服务）

| 目录 | 语言 / 框架 | 端口 | 说明 |
|---|---|---|---|
| `apps/web` | TypeScript · Next.js 15 · Tailwind · shadcn/ui | 3000 | 前端，`/api/*` 由 Next.js 代理到 core |
| `services/core` | Python 3.12 · FastAPI · SQLAlchemy 2 · LangGraph | 8000 | 业务 + Agent + 行业包 + RAG |
| `services/gateway` | Python 3.12 · FastAPI · LiteLLM 库 | 8100 | 模型网关：注册表 + 兼容层，对外 OpenAI 格式 |
| `infra/` | — | — | Nginx 等部署配置 |
| `docs/` | — | — | 规范、架构、接口契约、ai-log |
| `prototype/` | — | — | UI 原型（只读参考，不要改） |

数据库：PostgreSQL 16 + pgvector（`db`，5432）。

## 3. 常用命令

```bash
# 全部服务（Docker）
docker compose up -d --build

# 网关（本地开发）
cd services/gateway && uv sync && uv run uvicorn app.main:app --reload --port 8100
cd services/gateway && uv run pytest

# core（本地开发，需要先 docker compose up -d db）
cd services/core && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload --port 8000
cd services/core && uv run pytest

# 前端
cd apps/web && pnpm install && pnpm dev
cd apps/web && pnpm lint && pnpm typecheck && pnpm test

# 首次启动后导入演示数据（--with-kb 需要配置 Embedding 模型）
docker compose exec core python -m seed

# 端到端测试（需要 docker compose 环境在运行）
uv run --python 3.12 --with httpx --with pytest pytest tests/e2e -q
```

> Windows 下用 curl 调试时用 `127.0.0.1` 而不是 `localhost`（后者可能解析到 IPv6，请求会卡住）；中文请求体用 UTF-8 文件发送（`--data-binary @body.json`）。

## 4. 硬性规则（违反就不能合并）

**架构**
1. 前端只调用 core 的 `/api/*`；core 只通过 `app/llm/client.py` 调用网关；网关之外不出现任何模型厂商的 SDK 或地址。
2. core 分层：`routers`（只做参数和响应）→ `services`（业务逻辑、权限、规则）→ `models`（ORM）。业务逻辑不能写进 router。
3. Agent 工具是 service 的薄包装：校验参数 → 调 service → 返回 `{ok, summary, data}`；工具里不写 SQL。
4. 数据权限在 service 层统一过滤（销售：本人；主管：本团队；管理员：全部），不靠前端隐藏。
5. 价格、毛利、提成、是否超标等数字**只能由规则代码计算**，阈值放 `rules.yaml`，不能硬编码，也不能让大模型算。
6. 行业相关的东西只放 `services/core/app/packs/<pack_id>/`，新增行业不改 agent 和 crm 代码。
7. 网关新增模型只改 `services/gateway/models.yaml`；兼容层（`app/compat/`）写成纯函数。

**接口**
8. REST 统一响应：`{"code": 0, "message": "ok", "data": ..., "request_id": "..."}`；错误码见 `docs/开发规范.md` §8.2。
9. 请求 ID 用请求头 `X-Request-ID` 在 web → core → gateway 之间透传。
10. 金额一律用整数「分」存储和传输，前端负责格式化。

**代码**
11. Python：全部写类型注解；用 ruff 格式化和检查；入参出参用 Pydantic；业务异常抛 `BizError(code, message)`。
12. TypeScript：`strict` 模式，禁止 `any`；服务端数据用 TanStack Query；样式只用 Tailwind + shadcn 组件，颜色、间距按 `docs/开发规范.md` §10.4。
13. 标识符用英文，注释和文档可以用中文。单个函数不超过 50 行，单个文件不超过 400 行。
14. 配置只从环境变量读取；**禁止提交真实 Key**，只改 `.env.example`。

**测试**
15. 新增的 service、规则、兼容层函数必须有单元测试；新增接口至少 1 个成功用例 + 1 个错误码用例。
16. 测试不依赖外网和真实 Key：网关用录制样本（`tests/fixtures/`），core 用 mock 网关；前端纯函数用 Vitest（`lib/__tests__/`）。
17. 修了 bug 要补一个能复现它的测试（回归测试）。

## 5. AI Coding 工作方式（课程评分重点）
1. 一次只做一个小任务，先在 `docs/ai-log/` 写任务卡（模板见 `docs/开发规范.md` §11.5）。
2. 生成代码后按 §11.4 审查清单自查，跑测试。
3. 把 AI 写错、人工修正的地方记进 ai-log——这是评分「对 AI 代码的校验与兜底」的证据。
4. 提交信息：`<type>(<scope>): <描述>`，AI 生成为主加 `[AI]`，人工修正加 `[AI-fix]`。

## 6. 完成的标准（Definition of Done）
- [ ] 代码符合上面的硬性规则
- [ ] `ruff check` / `pnpm lint` / `pnpm typecheck` 通过
- [ ] 相关测试通过
- [ ] 改了接口就同步更新 `docs/api/openapi.yaml`（或 FastAPI 自动生成的 schema）
- [ ] 写了 ai-log
