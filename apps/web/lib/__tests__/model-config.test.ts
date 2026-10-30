import { describe, expect, it } from "vitest"

import type { ModelCard, ModelConfig } from "@/hooks/useModelConfig"
import { aiStatus, candidates, customAlias, fromOption, suggestId, toOption, validId } from "@/lib/model-config"

const card = (alias: string, kind: ModelCard["kind"], extra: Partial<ModelCard> = {}): ModelCard => ({
  alias,
  model: alias,
  link: "openai_compat",
  kind,
  tools: false,
  dims: null,
  available: true,
  unavailable_reason: null,
  provider: "测试",
  ...extra,
})

describe("模型接入", () => {
  it("自定义模型别名与后端一致", () => {
    expect(customAlias("kimi", "Moonshot-V1 8K")).toBe("kimi-moonshot-v1-8k")
    expect(customAlias("glm", "glm-4.5")).toBe("glm-glm-4.5")
    expect(customAlias("x", "Qwen/Qwen3-8B")).toBe("x-qwen-qwen3-8b")
  })

  it("厂商标识：按名称猜，中文名猜不出时留空", () => {
    expect(suggestId("Kimi")).toBe("kimi")
    expect(suggestId("Silicon Flow")).toBe("silicon-flow")
    expect(suggestId("月之暗面")).toBe("")
    expect(validId("k")).toBe(false)
    expect(validId("9kimi")).toBe(false)
    expect(validId("my-llm2")).toBe(true)
  })

  it("候选：对话只要能调用工具的，向量只要维度对得上或还没测的", () => {
    const config = {
      embedding_dims: 1024,
      models: [
        card("a", "chat", { tools: true }),
        card("b", "chat"),
        card("e1", "embedding", { dims: 1024 }),
        card("e2", "embedding", { dims: 1536 }),
        card("e3", "embedding"),
        card("r", "rerank"),
      ],
    } as ModelConfig
    expect(candidates(config, "chat").map((m) => m.alias)).toEqual(["a"])
    expect(candidates(config, "embedding").map((m) => m.alias)).toEqual(["e1", "e3"])
    expect(candidates(config, "rerank").map((m) => m.alias)).toEqual(["r"])
  })

  it("协议选项：空字符串和 default 互转", () => {
    expect(toOption("")).toBe("default")
    expect(fromOption(toOption(""))).toBe("")
    expect(fromOption("native")).toBe("native")
  })

  it("默认模型摘要：按分组顺序取第一个可用的，其余可用的算备用", () => {
    const config = {
      groups: { "chat-agent": ["a", "b", "c"], embed: ["e"], rerank: [] },
      models: [
        card("a", "chat", { available: false, provider: "腾讯混元" }),
        card("b", "chat", { provider: "DeepSeek" }),
        card("c", "chat", { provider: "通义千问（阿里云百炼）" }),
        card("e", "embedding", { available: false }),
      ],
    } as unknown as ModelConfig
    expect(aiStatus(config)).toEqual([
      { label: "对话", value: "DeepSeek", backups: ["通义千问"] },
      { label: "知识库", value: null, backups: [] },
      { label: "重排", value: null, backups: [] },
    ])
  })
})
