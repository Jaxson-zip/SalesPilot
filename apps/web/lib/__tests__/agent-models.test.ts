import { describe, expect, it } from "vitest"

import { modelOptions, ruleModeHint } from "@/lib/agent-models"
import type { ChatModels } from "@/types/api"

const data: ChatModels = {
  items: [
    { id: "deepseek-chat", type: "model", available: true, members: [] },
    { id: "kimi-k2", type: "model", available: false, members: [] },
    { id: "chat-agent", type: "group", available: true, members: ["deepseek-chat", "kimi-k2"] },
  ],
  default: "chat-agent",
  any_available: true,
  gateway_ok: true,
}

describe("modelOptions", () => {
  it("分组排在前面并写明当前先用哪个模型；新接入的模型直接显示别名；未配置的标记不可用", () => {
    expect(modelOptions(data)).toEqual([
      { value: "chat-agent", label: "自动", available: true, kind: "auto", detail: "当前 DeepSeek" },
      { value: "deepseek-chat", label: "DeepSeek", available: true, kind: "model" },
      { value: "kimi-k2", label: "kimi-k2", available: false, kind: "model" },
    ])
  })

  it("只显示对话默认分组，不把其他分组的内部 ID 露出来", () => {
    const withOther: ChatModels = {
      ...data,
      items: [...data.items, { id: "chat-default", type: "group", available: true, members: ["deepseek-chat"] }],
    }
    expect(modelOptions(withOther).map((m) => m.value)).not.toContain("chat-default")
  })

  it("分组里第一个模型没配 Key 时，显示实际会用到的那个", () => {
    const opts = modelOptions({
      ...data,
      items: [
        { id: "kimi-k2", type: "model", available: false, members: [] },
        { id: "deepseek-chat", type: "model", available: true, members: [] },
        { id: "chat-agent", type: "group", available: true, members: ["kimi-k2", "deepseek-chat"] },
      ],
    })
    expect(opts[0].detail).toBe("当前 DeepSeek")
  })

  it("接口未返回时用内置选项", () => {
    expect(modelOptions(undefined)[0]).toEqual({ value: "chat-agent", label: "自动", available: true, kind: "auto" })
  })
})

describe("ruleModeHint", () => {
  it("有可用模型时不提示", () => {
    expect(ruleModeHint(data)).toBeNull()
    expect(ruleModeHint(undefined)).toBeNull()
  })

  it("没配 Key / 网关没连上时提示规则模式", () => {
    expect(ruleModeHint({ ...data, any_available: false })).toContain("未配置大模型 Key")
    expect(ruleModeHint({ ...data, any_available: false, gateway_ok: false })).toContain("网关未连接")
  })
})
