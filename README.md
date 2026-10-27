# SalesPilot · AI 销售 CRM

腾讯 AI Coding 课程作业 · 方向二 · 场景 3「业务智能体」。

面向 ToB 销售的 CRM：销售用一句话完成「查客户 → 记跟进 → 推进商机 → 出方案报价 → 报销」，AI 通过 **function calling** 调用真实的业务工具读写数据，写操作必须经用户确认；价格、毛利、提成、报销标准一律由规则代码计算；行业知识以可插拔的「行业包」提供（大模型部署 / 企业办公 IT）。

> ⚠️ 项目中的客户、产品价格、提成比例、报销标准均为**模拟数据**。

## 功能一览

| 模块 | 能做什么 |
|---|---|
| AI 方案工作台 | 对话出方案报价（显存估算 → 配置 → 毛利校验 → 不达标自动重配 → 确认后生成报价单）；对话记跟进、改商机阶段、安排下一步、报销、查制度（带出处）；主管处理审批；执行过程（思考 → 调用 → 结果）可视化 |
| 客户 / 商机 | 列表筛选排序导出、多选批量操作、主管转移负责人；商机看板拖拽（可撤销）、赢单 / 输单确认；下一步任务、阶段默认赢率、久未跟进提醒 |
| 报价 / 合同 | 报价调价（规则重算毛利和是否需审批）、正式报价单打印 / 存 PDF（不含成本毛利）；合同、回款登记、提成按回款确认 |
| 报销 / 审批 | 按类型填写（客户招待选参与人、差旅填行程、住宿按城市每晚标准校验）、模板和报销须知、上传票据自动存草稿、超标自动转主管审批 |
| 权限 | 销售只改自己的数据；主管看团队、审批、登记回款；管理员只读并配置行业包；无权按钮不显示 |
| 其他 | 通知铃铛、工作台待办、「使用说明」页 |

## 架构

```
浏览器 ── web（Next.js）── /api/* ──▶ core（FastAPI + LangGraph）──▶ gateway（FastAPI + LiteLLM）──▶ 混元 / DeepSeek / 通义 …
                                         │
                                         └──▶ PostgreSQL 16 + pgvector（业务数据 · 知识库向量 · 会话状态）
```

| 服务 | 技术 | 端口 |
|---|---|---|
| web | TypeScript · Next.js 15 · React 19 · Tailwind · shadcn/ui · TanStack Query | 3000 |
| core | Python 3.12 · FastAPI · SQLAlchemy 2 · LangGraph · pgvector | 8000 |
| gateway | Python 3.12 · FastAPI · LiteLLM 库（模型注册表 + 兼容层） | 8100 |
| db | PostgreSQL 16 + pgvector | 5432 |
| nginx（可选） | `/` → web，`/api` → core（SSE 关缓冲） | 8080 |

详见 [架构设计](docs/架构设计.md)、[架构图](docs/架构图.html)、[开发规范](docs/开发规范.md)、[架构完成度与缺项说明](docs/架构完成度与缺项说明.md)。

## 快速开始（Docker，推荐）

环境：Docker Desktop（含 Compose v2）。Windows 下访问请用 `127.0.0.1`，不要用 `localhost`（可能解析到 IPv6 导致卡住）。

```bash
# 1. 配置（不填模型 Key 也能启动：AI 走「规则模式」，回复为固定模板）
cp .env.example .env

# 2. 构建并启动 db / gateway / core / web
docker compose up -d --build

# 3. 导入演示数据（客户、商机、报价、报销、审批、任务、通知）
docker compose exec core python -m seed
```

打开 http://127.0.0.1:3000 。左下角用户卡片可以切换演示角色：

| 角色 | 姓名 | 适合演示 |
|---|---|---|
| 销售 | 张晨 | AI 出方案、对话报销、看板拖拽、写跟进、安排下一步 |
| 销售主管 | 李薇 | 审批、团队商机、转移负责人、登记回款 |
| 系统管理员 | 周敏 | 行业包配置、只读查看全公司数据 |

### 接入大模型

在 `.env` 里填至少一家的 Key（地址已预填官方兼容接口），然后重启网关和 core：

```bash
docker compose up -d gateway core
```

- 网关模型列表：http://127.0.0.1:8100/v1/models （需要 `Authorization: Bearer <GATEWAY_INTERNAL_KEY>`）
- 新增模型只改 `services/gateway/models.yaml`，并跑契约测试：`cd services/gateway && uv run pytest tests/contract -k <别名>`

### 知识库入库（需要 Embedding 模型）

```bash
docker compose exec core python -m app.rag.ingest --scope all
docker compose exec core python -m app.rag.evaluate          # 评测：Top-4 命中率 / 拒答率
```

core 启动时如果知识库为空且有可用的 Embedding 模型，会自动入库一次。资料来源、切块和检索参数见 [知识库构建说明](docs/知识库构建说明.md)。

### 通过 Nginx 访问（与云端部署一致）

```bash
docker compose --profile prod up -d       # 额外启动 nginx，访问 http://127.0.0.1:8080
```

云端部署（腾讯云轻量服务器）：设置 `NGINX_PORT=80`、修改 `JWT_SECRET` 和 `GATEWAY_INTERNAL_KEY`，并去掉 `docker-compose.yml` 中 db / gateway / core 的端口映射，只对外暴露 nginx。

## 接口

| 文档 | 位置 |
|---|---|
| 接口契约（字段、错误码、权限矩阵、Agent 事件） | [docs/api/业务模块接口契约.md](docs/api/业务模块接口契约.md) |
| OpenAPI（从代码导出） | [docs/api/openapi.yaml](docs/api/openapi.yaml)，运行中可看 http://127.0.0.1:8000/docs |
| 模型兼容矩阵 | [docs/模型兼容矩阵.md](docs/模型兼容矩阵.md) |

统一响应 `{"code": 0, "message": "ok", "data": ..., "request_id": "..."}`；金额单位为「分」；请求 ID 通过 `X-Request-ID` 在 web → core → gateway 之间透传。改了接口后运行 `cd services/core && uv run python scripts/export_openapi.py`（有测试检查是否最新）。

## 本地开发

```bash
docker compose up -d db gateway                              # 只用容器跑数据库和网关
cd services/core && uv sync && uv run alembic upgrade head && uv run python -m seed
cd services/core && uv run uvicorn app.main:app --reload --port 8000
cd apps/web && pnpm install && pnpm dev                      # http://127.0.0.1:3000
```

## 测试

| 层 | 命令 | 说明 |
|---|---|---|
| core 单元 + 接口 | `cd services/core && uv run pytest` | 自动使用独立测试库 `crm_test`；模型用剧本代替，不需要 Key |
| gateway | `cd services/gateway && uv run pytest` | 兼容层用录制样本；契约测试需要真实 Key，没有时跳过 |
| 前端单元 | `cd apps/web && pnpm lint && pnpm typecheck && pnpm test` | Vitest |
| 接口端到端 | `uv run --python 3.12 --with httpx --with pytest pytest tests/e2e -q` | 需要 Docker 环境在运行 |
| 浏览器自动化 | `cd apps/web && PW_CHANNEL=msedge pnpm test:e2e` | Playwright，直接用 Windows 自带的 Edge；`E2E_BASE_URL=http://127.0.0.1:8080` 可经 Nginx 测 |

跑完端到端 / 浏览器测试后恢复干净的演示数据：`docker compose exec core python -m seed --reset`。测试结果和联调过程见 [测试与联调报告](docs/测试与联调报告.md)。

## 目录

```
apps/web               前端（页面、组件、hooks、纯函数 lib、Playwright e2e）
services/core          业务 + Agent + 行业包 + RAG
  app/crm              routers → services → models（权限在 service 层）
  app/agent            LangGraph 状态图、function calling、工具
  app/packs            行业包（llm_deploy / it_office）
  app/rag              加载（Markdown / PDF / Excel）、切块、入库、检索、评测
  app/rules            rules.yaml（标准 / 阈值）+ templates.yaml（业务模板）+ 计算器
services/gateway       模型网关（注册表 models.yaml、兼容层、契约测试）
infra/nginx            反向代理配置
tests/e2e              接口端到端测试
docs/                  架构、规范、接口契约、知识库说明、测试报告、AI Coding 记录（ai-log）
prototype/             UI 原型
```

## AI Coding 记录

开发全过程由 Claude Code 辅助完成，每个阶段的任务、AI 写错的地方和人工修正都记录在 [docs/ai-log/](docs/ai-log/)；项目规范见 [AGENTS.md](AGENTS.md)。
