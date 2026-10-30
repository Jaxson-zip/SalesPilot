import { describe, expect, it } from "vitest"

import type { BuiltinProvider, ModelCard, ModelConfig } from "@/hooks/useModelConfig"
import {
  builtinDirty,
  builtinForm,
  candidates,
  customAlias,
  fromOption,
  keySourceText,
  moveItem,
  suggestId,
  toOption,
  validId,
} from "@/lib/model-config"

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

const builtin: BuiltinProvider = {
  var: "DEEPSEEK_API_KEY",
  label: "DeepSeek",
  hint: "",
  key_source: "web",
  tail: "abcd",
  saved_by: "周敏",
  saved_at: "2026-10-30T08:00:00Z",
  broken: false,
  base: "",
  default_base: "https://api.deepseek.com/v1",
  protocol: "",
  adapter: "",
  available: true,
  models: [],
}

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

  it("调整顺序：越界不动", () => {
    expect(moveItem(["a", "b", "c"], 1, -1)).toEqual(["b", "a", "c"])
    expect(moveItem(["a", "b"], 0, -1)).toEqual(["a", "b"])
    expect(moveItem(["a", "b"], 1, 1)).toEqual(["a", "b"])
  })

  it("内置厂商表单：填了 Key 或改了地址 / 协议才算改动", () => {
    const form = builtinForm(builtin)
    expect(form.protocol).toBe("default")
    expect(builtinDirty(builtin, form)).toBe(false)
    expect(builtinDirty(builtin, { ...form, key: " sk-new " })).toBe(true)
    expect(builtinDirty(builtin, { ...form, base: "https://proxy/v1" })).toBe(true)
    expect(builtinDirty(builtin, { ...form, protocol: "native", adapter: "deepseek" })).toBe(true)
    expect(fromOption(toOption(""))).toBe("")
  })

  it("Key 来源说明", () => {
    expect(keySourceText(builtin, () => "10-30 16:00")).toBe("网页填写 · 末 4 位 abcd · 周敏 10-30 16:00 保存")
    expect(keySourceText({ ...builtin, key_source: "env" }, String)).toBe("服务器 .env 的 DEEPSEEK_API_KEY")
  })
})
