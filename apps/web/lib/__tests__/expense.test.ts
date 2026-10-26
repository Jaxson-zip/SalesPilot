import { describe, expect, it } from "vitest"

import {
  attachmentSummary,
  checkFromPolicy,
  checkFromPrecheck,
  formatBytes,
  missingAttachmentReason,
  toExpenseCreate,
  toPrecheckBody,
  validateAttachmentFile,
  type ExpenseFormValues,
} from "@/lib/expense"

const base: ExpenseFormValues = {
  type: "entertainment",
  amount: "860",
  headcount: "4",
  occurred_on: "2026-10-23",
  customer_id: "c1",
  participants: "客户：王律师；我方：张晨",
  reason: " 方案沟通晚餐 ",
}

describe("toExpenseCreate", () => {
  it("金额转分、去空格、带幂等键", () => {
    expect(toExpenseCreate(base, "key-1")).toEqual({
      ok: true,
      value: {
        type: "entertainment",
        amount: 86000,
        headcount: 4,
        occurred_on: "2026-10-23",
        reason: "方案沟通晚餐",
        participants: "客户：王律师；我方：张晨",
        customer_id: "c1",
        idempotency_key: "key-1",
      },
    })
  })

  it("可选字段为空时不传", () => {
    const r = toExpenseCreate({ ...base, type: "transport", participants: "", customer_id: null })
    expect(r.ok && r.value).toEqual({
      type: "transport",
      amount: 86000,
      headcount: 4,
      occurred_on: "2026-10-23",
      reason: "方案沟通晚餐",
    })
  })

  it("逐项给出错误", () => {
    const r = toExpenseCreate({ ...base, amount: "0", headcount: "0", occurred_on: "", reason: "", participants: "" })
    expect(r.ok).toBe(false)
    if (!r.ok)
      expect(Object.keys(r.errors).sort()).toEqual(["amount", "headcount", "occurred_on", "participants", "reason"])
  })
})

describe("toPrecheckBody", () => {
  it("金额和人数合法即可预校验", () => {
    expect(toPrecheckBody({ ...base, reason: "" })).toMatchObject({ amount: 86000, headcount: 4, reason: "precheck" })
    expect(toPrecheckBody({ ...base, amount: "" })).toBeNull()
  })
})

describe("missingAttachmentReason（契约 §5 submit 前置条件）", () => {
  it("客户招待需要发票 + 小票", () => {
    expect(missingAttachmentReason("entertainment", [])).toBe("客户招待需同时上传发票和消费小票，还缺少发票、消费小票")
    expect(missingAttachmentReason("entertainment", [{ kind: "invoice" }])).toContain("还缺少消费小票")
    expect(missingAttachmentReason("entertainment", [{ kind: "invoice" }, { kind: "receipt" }])).toBeNull()
  })
  it("其他类型至少一张发票，小票不能代替", () => {
    expect(missingAttachmentReason("hotel", [{ kind: "receipt" }])).toBe("需要至少上传一张发票，还缺少发票")
    expect(missingAttachmentReason("transport", [{ kind: "invoice" }])).toBeNull()
  })
})

describe("validateAttachmentFile", () => {
  it("类型与大小", () => {
    expect(validateAttachmentFile({ name: "a.pdf", size: 1000, type: "application/pdf" })).toBeNull()
    expect(validateAttachmentFile({ name: "A.JPG", size: 1000, type: "" })).toBeNull()
    expect(validateAttachmentFile({ name: "a.docx", size: 1000, type: "application/msword" })).toContain("只支持")
    expect(validateAttachmentFile({ name: "a.png", size: 11 * 1024 * 1024, type: "image/png" })).toContain("10 MB")
  })
})

describe("formatBytes / attachmentSummary", () => {
  it("格式化", () => {
    expect(formatBytes(512)).toBe("512 B")
    expect(formatBytes(880640)).toBe("860 KB")
    expect(formatBytes(1258291)).toBe("1.2 MB")
    expect(attachmentSummary([])).toBe("还没有上传票据")
    expect(attachmentSummary([{ kind: "invoice" }, { kind: "receipt" }])).toBe("已上传 2 个文件 · 发票 1 · 小票 1")
  })
})

describe("制度校验结果转换", () => {
  it("precheck 与 policy_check 统一成同一结构", () => {
    expect(
      checkFromPrecheck({
        per_person: 21500,
        limit_per_person: 15000,
        over_amount: 26000,
        need_approval: true,
        reason: "超标",
      }),
    ).toEqual({ over: true, per_person: 21500, limit_per_person: 15000, over_amount: 26000, summary: "超标" })
    expect(
      checkFromPolicy({ passed: true, per_person: 100, limit_per_person: 15000, over_amount: 0, rule_ref: "§4.2" }),
    ).toEqual({ over: false, per_person: 100, limit_per_person: 15000, over_amount: 0, note: "依据 §4.2" })
  })
})
