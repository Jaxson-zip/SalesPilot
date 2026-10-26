import { describe, expect, it } from "vitest"

import {
  activityActionLabel,
  EXPENSE_STATUS_META,
  EXPENSE_TYPE_META,
  labelOf,
  QUOTE_STATUS_META,
  STAGE_META,
  STAGE_ORDER,
} from "@/lib/labels"

describe("状态标签（照抄契约 §0）", () => {
  it("商机阶段", () => {
    expect(STAGE_ORDER.map((s) => STAGE_META[s].label)).toEqual(["线索", "需求确认", "方案报价", "商务谈判", "赢单"])
    expect(STAGE_META.lost.label).toBe("输单")
  })

  it("报价与报销状态", () => {
    expect(QUOTE_STATUS_META.pending_approval.label).toBe("待主管审批")
    expect(QUOTE_STATUS_META.sent.label).toBe("已发送客户")
    expect(QUOTE_STATUS_META.accepted.label).toBe("已成交")
    expect(EXPENSE_STATUS_META.paid.label).toBe("已打款")
    expect(EXPENSE_TYPE_META.hotel.label).toBe("差旅住宿")
  })

  it("未知取值回落为原文 + 灰色", () => {
    expect(labelOf(QUOTE_STATUS_META, "archived")).toEqual({ label: "archived", color: "gray" })
    expect(labelOf(STAGE_META, "won").color).toBe("green")
  })

  it("动态 action 映射，未知 action 原样显示", () => {
    expect(activityActionLabel("stage_changed")).toBe("更新了商机阶段")
    expect(activityActionLabel("followup.phone")).toBe("记录了电话跟进")
    expect(activityActionLabel("something.new")).toBe("something.new")
  })

  it("按 core 实际发出的「对象类型 + 动作」翻译（回归：曾直接显示 create / attachment_added）", () => {
    expect(activityActionLabel("create", "quote")).toBe("生成了报价单")
    expect(activityActionLabel("attachment_added", "expense")).toBe("上传了票据")
    expect(activityActionLabel("approval_approve", "expense")).toBe("主管通过了报销")
    expect(activityActionLabel("payment", "contract")).toBe("登记了回款")
    expect(activityActionLabel("create", "unknown_subject")).toBe("创建了记录")
  })
})
