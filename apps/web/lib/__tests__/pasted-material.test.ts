import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  digestPrompt,
  MATERIAL_MAX_CHARS,
  pastedMaterial,
  stashPastedMaterial,
  takePastedMaterial,
} from "@/lib/materials"

describe("粘贴纪要交给 AI", () => {
  // 单元测试跑在 Node 环境：用内存实现代替 sessionStorage
  beforeEach(() => {
    const store = new Map<string, string>()
    vi.stubGlobal("sessionStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it("当作文字材料；超长截断并标记", () => {
    const m = pastedMaterial("  王总：预算批了  ", "明理律所")
    expect(m).toEqual({
      name: "明理律所 沟通纪要.txt",
      kind: "text",
      text: "王总：预算批了",
      chars: 7,
      truncated: false,
    })
    const long = pastedMaterial("字".repeat(MATERIAL_MAX_CHARS + 5), "甲")
    expect(long.text).toHaveLength(MATERIAL_MAX_CHARS)
    expect(long.truncated).toBe(true)
  })

  it("提示语带上客户和商机", () => {
    expect(digestPrompt("明理律所")).toContain("「明理律所」的跟进记录")
    expect(digestPrompt("明理律所", "合同审查私有化")).toContain("「明理律所」的「合同审查私有化」商机")
  })

  it("暂存只能取一次", () => {
    expect(stashPastedMaterial(pastedMaterial("内容", "甲"))).toBe(true)
    expect(takePastedMaterial()?.text).toBe("内容")
    expect(takePastedMaterial()).toBeNull()
  })

  it("存储被禁用时返回 false，不抛错", () => {
    vi.stubGlobal("sessionStorage", {
      setItem: () => {
        throw new Error("blocked")
      },
    })
    expect(stashPastedMaterial(pastedMaterial("内容", "甲"))).toBe(false)
    expect(takePastedMaterial()).toBeNull()
  })
})
