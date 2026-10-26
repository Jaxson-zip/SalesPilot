import { describe, expect, it } from "vitest"

import { insertTemplate, isUnfilledTemplate, pickReason } from "@/lib/templates"

const TPL = "沟通对象：\n客户反馈：\n下一步："

describe("insertTemplate", () => {
  it("空内容直接替换，已有内容追加在后面，不重复插入", () => {
    expect(insertTemplate("", TPL)).toBe(TPL)
    expect(insertTemplate("王律师来电", TPL)).toBe(`王律师来电\n${TPL}`)
    expect(insertTemplate(TPL, TPL)).toBe(TPL)
  })
})

describe("isUnfilledTemplate", () => {
  it("只有标题没有内容时视为未填写", () => {
    expect(isUnfilledTemplate(TPL)).toBe(true)
    expect(isUnfilledTemplate("沟通对象：王律师\n客户反馈：\n下一步：")).toBe(false)
    expect(isUnfilledTemplate("普通的一句话")).toBe(false)
    expect(isUnfilledTemplate("")).toBe(false)
  })
})

describe("pickReason", () => {
  it("常用原因放在前面，保留补充说明", () => {
    expect(pickReason("", "选择了竞品")).toBe("选择了竞品")
    expect(pickReason("对方报价低 20%", "选择了竞品")).toBe("选择了竞品；对方报价低 20%")
    expect(pickReason("选择了竞品；对方报价低 20%", "选择了竞品")).toBe("选择了竞品；对方报价低 20%")
  })
})
