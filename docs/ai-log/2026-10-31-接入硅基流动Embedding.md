# 接入硅基流动 BGE-M3 向量模型与 BGE-Reranker 重排模型

- 日期：2026-10-31 · 开发者：Antigravity · 模块：gateway / core / docs

## 目标
1. 排查 Embedding 与 Rerank 服务失败与超时问题；
2. 解决通义百炼因本地代理网络分流导致的 SSL 握手超时以及模型名称配置错误（v4 不存在）；
3. 接入硅基流动（SiliconFlow）的 `BAAI/bge-m3`（1024 维）向量模型以及 `BAAI/bge-reranker-v2-m3` 重排模型；
4. 完成知识库全库重新向量化与重排命中率评测。

## 做了什么
1. **排查并定位根因**：
   - 本地代理（TUN 模式）劫持并分流 `dashscope.aliyuncs.com`，导致连阿里云接口全部握手超时（每次请求卡 30 秒超时）；
   - `models.yaml` 中原先配置的 `text-embedding-v4` 不存在（官方最新且为 1024 维的是 `text-embedding-v3`）；
   - 原先的重排模型 `rerank-qwen` 指向阿里云，同样因代理连接超时报错并降级。
2. **网关配置接入硅基流动向量与重排模型**：
   - 在 `services/gateway/models.yaml` 中新增 `embed-sf`（模型 `BAAI/bge-m3`，1024 维），并将 `embed` 分组指向 `[embed-sf]`；
   - 新增 `rerank-sf`（采用 native hosted_vllm 协议，模型 `hosted_vllm/BAAI/bge-reranker-v2-m3`），并将 `rerank` 分组指向 `[rerank-sf]`；
   - 顺带将 `embed-qwen` 修正为 `text-embedding-v3`。
3. **环境变量与系统设置适配**：
   - 在 `.env.example` 补充硅基流动配置项示例；在 `.env` 中安全写入用户 Key；
   - 在 `services/core/app/crm/services/model_config_service.py` 的 `LABELS` 中补充 `SILICONFLOW_API_KEY` 的显示与指引信息。
4. **服务重启、全量入库与评测**：
   - 重启网关及业务容器，验证网关 `/v1/embeddings` 与 `/v1/rerank` 全部返回 200 OK；
   - 执行 `python -m app.rag.ingest --scope all --reset` 完成全 scope 知识库切块向量重构；
   - 执行 `python -m app.rag.evaluate` 进行检索与重排效果对比评测。

## 验证
- 网关单元测试：116 passed
- 核心库 RAG 单元测试：35 passed
- 网关 `/v1/embeddings` 真实测试：200 OK，向量维度 1024
- 网关 `/v1/rerank` 真实测试：200 OK，毫秒级返回 Cohere 规范重排列表
- 知识库切块重构：全部 39 个块入库成功
- RAG 重排效果评测：在 36 道有答案的业务制度问答中，**Top-1 命中率由纯向量的 75% 显著提升至重排后的 92%**！

## 补充（Claude Code 检查）
- 第一次全量入库时，容器里还没有扩充后的软件外包文档，`pack:software_outsourcing` 只有《软件外包报价说明》8 块（自动入库只补空分区，不会补漏掉的文档）。补跑 `python -m app.rag.ingest --scope pack:software_outsourcing` 后共 29 块、5 份文档。上面「全部 39 个块」不准确，现在全库是 60 块：company 20、it_office 2、llm_deploy 9、software_outsourcing 29。
- `LABELS` 在拆分重构后已移到 `app/crm/services/model_config_store.py`。
- 重排启用后的评测（36 道有答案 + 7 道应拒答）：

| 阈值 | Top-4 命中率 | 拒答率 |
|---|---|---|
| 0.4 | 94% | 0% |
| 0.5（当前） | 94% | 57% |
| 0.6 | 86% | 86% |

  重排后 Top-1 从 75% 升到 92%。BGE-M3 相似度整体偏高，五险一金、电脑丢了怎么赔、软著登记费这类知识库没有的问题也能过 0.5。
- 学习模式实测这 3 个问题和「年假几天」：AI 都回答「知识库里没有找到」，没有编造数字，第二道防线（提示词要求只依据工具结果回答）兜住了。
- 发现：新会话默认按 `DEFAULT_PACK=llm_deploy` 检索，问「开发到一半加功能怎么收费」时没搜软件外包资料，所以没用上《需求变更与验收》。要让团队默认产品线设为软件外包，或者改 `DEFAULT_PACK`。
