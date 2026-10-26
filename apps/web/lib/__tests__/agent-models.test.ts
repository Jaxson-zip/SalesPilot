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
  it("分组排在前面；内置中文名，新接入的模型直接显示别名；未配置的标记不可用", () => {
    expect(modelOptions(data)).toEqual([
      { value: "chat-agent", label: "自动（失败切换）", available: true },
      { value: "deepseek-chat", label: "DeepSeek", available: true },
      { value: "kimi-k2", label: "kimi-k2", available: false },
    ])
  })

  it("接口未返回时用内置选项", () => {
    expect(modelOptions(undefined)[0]).toEqual({ value: "chat-agent", label: "自动（失败切换）", available: true })
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
