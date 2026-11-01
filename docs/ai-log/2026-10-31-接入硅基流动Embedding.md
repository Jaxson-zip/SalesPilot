# 接入硅基流动 BGE-M3 向量模型与知识库重新入库

- 日期：2026-10-31 · 开发者：Antigravity · 模块：gateway / core / docs

## 目标
排查 Embedding 服务失败原因，解决通义百炼因本地代理网络分流导致的 SSL 握手超时以及模型名称配置错误问题；接入硅基流动（SiliconFlow）的 `BAAI/bge-m3`（1024 维）向量模型，完成全库重新向量化与入库。

## 做了什么
1. **排查并定位根因**：
   - 发现本地代理软件（TUN 模式）将 `dashscope.aliyuncs.com` 流量分流导致连接超时（`_ssl.c:1015: The handshake operation timed out`）；
   - 发现 `models.yaml` 中原先配置的 `text-embedding-v4` 不存在（官方最新且为 1024 维的是 `text-embedding-v3`）。
2. **网关配置接入硅基流动**：
   - 在 `services/gateway/models.yaml` 中新增 `embed-sf`（模型 `BAAI/bge-m3`，1024 维），并将 `embed` 分组指向 `[embed-sf]`；
   - 顺便修正 `embed-qwen` 的模型名为 `text-embedding-v3`。
3. **环境变量与系统设置适配**：
   - 在 `.env.example` 补充硅基流动配置项示例；在 `.env` 中安全写入配置；
   - 在 `services/core/app/crm/services/model_config_service.py` 的 `LABELS` 中补充 `SILICONFLOW_API_KEY` 的显示与指引信息。
4. **服务重启与全量入库**：
   - 重启网关及业务容器，验证网关 `/v1/embeddings` 返回 1024 维向量；
   - 执行 `python -m app.rag.ingest --scope all --reset` 完成全 scope 知识库切块向量重构。

## 验证
- 网关单元测试：116 passed
- 网关 /v1/embeddings 真实测试：200 OK，向量维度 1024
- 知识库切块重构：company 20、pack:it_office 2、pack:llm_deploy 9、pack:software_outsourcing 8 全部入库成功

## 补充（Claude Code 检查）
- 上面的入库是在容器里还没有扩充后的文档时跑的，`pack:software_outsourcing` 只有《软件外包报价说明》8 块，另外 4 份新文档没进库（自动入库只补空分区，不会补漏掉的文档）。已补跑 `python -m app.rag.ingest --scope pack:software_outsourcing`：共 29 块，新增 21 块，5 份文档都已入库。
- 用 BGE-M3 跑 `python -m app.rag.evaluate`（36 道有答案的题 + 7 道应拒答的题）：

| 阈值 | Top-4 命中率 | 拒答率 |
|---|---|---|
| 0.4 | 94% | 0% |
| 0.5（当前） | 94% | 57% |
| 0.6 | 86% | 86% |

- 没命中的 2 道软件外包题：「开发到一半要加功能怎么收费」（前 4 条里没有《需求变更与验收》）、「审批流程为什么报价这么高」（被公司《合同审批与回款流程》抢走）。
- BGE-M3 的相似度整体偏高，和知识库无关的问题（五险一金、电脑丢了怎么赔、软著登记费）也能超过 0.5，拒答率比之前低，阈值要不要调还没定。
- 重排分组留空以后，每次检索仍然会去调 `/v1/rerank`，返回 502 后再退回纯向量排序。结果没错，但日志里每次都有一条告警。
