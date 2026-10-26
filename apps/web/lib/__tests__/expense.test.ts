import { describe, expect, it } from "vitest"

import {
  attachmentSummary,
  checkFromPolicy,
  checkFromPrecheck,
  formatBytes,
  headcountSummary,
  missingAttachmentReason,
  parseExtraGuests,
  participantCount,
  perPersonFen,
  toExpenseCreate,
  toggleId,
  toPrecheckBody,
  validateAttachmentFile,
  type ExpenseFormValues,
} from "@/lib/expense"

const base: ExpenseFormValues = {
  type: "entertainment",
  amount: "860",
  occurred_on: "2026-10-23",
  customer_id: "c1",
  opportunity_id: "o1",
  contact_ids: ["ct1", "ct2"],
  colleague_ids: ["u2"],
  extra_guests: "",
  reason: " 方案沟通晚餐 ",
}

describe("participantCount / headcountSummary（v3 §17）", () => {
  it("人数 = 客户联系人 + 同事 + 本人 + 其他人数", () => {
    expect(participantCount(base)).toBe(4)
    expect(participantCount({ ...base, extra_guests: "2" })).toBe(6)
    expect(participantCount({ contact_ids: [], colleague_ids: [], extra_guests: "" })).toBe(1)
    // 其他人数非法时按 0 计，不让人数跳动
    expect(participantCount({ ...base, extra_guests: "abc" })).toBe(4)
  })
  it("人均四舍五入到分", () => {
    expect(perPersonFen(100000, 3)).toBe(33333)
    expect(perPersonFen(100000, 0)).toBe(0)
  })
  it("共 N 人，人均 ¥xx；金额未填只显示人数", () => {
    expect(headcountSummary("860", 4)).toBe("共 4 人，人均 ¥215")
    expect(headcountSummary("", 4)).toBe("共 4 人")
  })
  it("parseExtraGuests：空 = 0，负数 / 小数非法", () => {
    expect(parseExtraGuests("")).toBe(0)
    expect(parseExtraGuests("3")).toBe(3)
    expect(parseExtraGuests("-1")).toBeNull()
    expect(parseExtraGuests("1.5")).toBeNull()
  })
  it("toggleId 勾选 / 取消", () => {
    expect(toggleId(["a"], "b")).toEqual(["a", "b"])
    expect(toggleId(["a", "b"], "a")).toEqual(["b"])
  })
})

describe("toExpenseCreate", () => {
  it("金额转分、去空格、参与人结构化、带幂等键", () => {
    expect(toExpenseCreate(base, "key-1")).toEqual({
      ok: true,
      value: {
        type: "entertainment",
        amount: 86000,
        headcount: 4,
        occurred_on: "2026-10-23",
        reason: "方案沟通晚餐",
        contact_ids: ["ct1", "ct2"],
        colleague_ids: ["u2"],
        extra_guests: 0,
        customer_id: "c1",
        opportunity_id: "o1",
        idempotency_key: "key-1",
      },
    })
  })

  it("非招待类型可以不关联客户；没有客户时不传商机", () => {
    const r = toExpenseCreate({
      ...base,
      type: "transport",
      customer_id: null,
      contact_ids: [],
      colleague_ids: [],
      extra_guests: "1",
    })
    expect(r.ok && r.value).toEqual({
      type: "transport",
      amount: 86000,
      headcount: 2,
      occurred_on: "2026-10-23",
      reason: "方案沟通晚餐",
      contact_ids: [],
      colleague_ids: [],
      extra_guests: 1,
    })
  })

  it("客户招待：必须关联客户", () => {
    const r = toExpenseCreate({ ...base, customer_id: null, contact_ids: [] })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.errors.customer_id).toBe("客户招待需关联客户")
  })

  it("客户招待：至少 1 名客户方参与人", () => {
    const r = toExpenseCreate({ ...base, contact_ids: [] })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.errors.contact_ids).toContain("至少选择 1 名")
  })

  it("逐项给出错误", () => {
    const r = toExpenseCreate({ ...base, amount: "0", extra_guests: "-1", occurred_on: "", reason: "" })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(Object.keys(r.errors).sort()).toEqual(["amount", "extra_guests", "occurred_on", "reason"])
  })
})

describe("toPrecheckBody", () => {
  it("金额合法即可预校验，人数随参与人实时变化", () => {
    expect(toPrecheckBody({ ...base, reason: "" })).toMatchObject({ amount: 86000, headcount: 4, reason: "precheck" })
    expect(toPrecheckBody({ ...base, extra_guests: "3" })).toMatchObject({ headcount: 7, extra_guests: 3 })
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
