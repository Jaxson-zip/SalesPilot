# SalesPilot · AI 销售 CRM

腾讯 AI Coding 课程作业 · 方向二 · 场景 3「业务智能体」。

销售用自然语言完成「记跟进 → 推进商机 → 出方案报价 → 成交算提成 → 报销」；Agent 通过工具调用读写真实业务数据；行业知识以可插拔的「行业包」提供（大模型部署 / 企业办公 IT）。

> ⚠️ 项目中的产品价格、提成比例、报销标准均为**模拟数据**。

## 架构

| 服务 | 技术 | 端口 |
|---|---|---|
| web | TypeScript · Next.js 15 · Tailwind · shadcn/ui | 3000 |
| core | Python 3.12 · FastAPI · SQLAlchemy 2 · LangGraph · pgvector | 8000 |
| gateway | Python 3.12 · FastAPI · LiteLLM 库（注册表 + 兼容层） | 8100 |
| db | PostgreSQL 16 + pgvector | 5432 |

详见 [架构设计](docs/架构设计.md)、[架构图](docs/架构图.html)、[开发规范](docs/开发规范.md)、[UI 原型](prototype/index.html)。

## 快速开始

```bash
cp .env.example .env          # 填入至少一家模型的 Key
docker compose up -d --build
```

- 前端：http://localhost:3000
- core 接口文档：http://localhost:8000/docs
- 网关模型列表：http://localhost:8100/v1/models

本地开发和测试命令见 [AGENTS.md](AGENTS.md) §3。

## 目录

```
apps/web           前端
services/core      业务 + Agent + 行业包 + RAG
services/gateway   模型网关
infra/             部署配置
docs/              规范、架构、接口契约、AI Coding 记录（ai-log）
prototype/         UI 原型
```
