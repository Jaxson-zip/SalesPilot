import { describe, expect, it } from "vitest"

import {
  approveConfirm,
  expenseSubmitConfirm,
  paymentConfirm,
  quoteActionConfirm,
  stageConfirm,
  stageNeedsConfirm,
} from "@/lib/confirm-texts"
import { canUndoStage, planStageMove, stageChangedText, stageUndoneText, UNDO_DURATION_MS } from "@/lib/stage-move"

describe("planStageMove", () => {
  it("非终态之间切换：立即生效，可撤销回原阶段", () => {
    expect(planStageMove("lead", "proposal")).toEqual({ kind: "direct", undoTo: "lead" })
    expect(planStageMove("negotiation", "qualified")).toEqual({ kind: "direct", undoTo: "negotiation" })
  })
  it("切到赢单需要确认，切到输单需要填原因", () => {
    expect(planStageMove("negotiation", "won")).toEqual({ kind: "confirm" })
    expect(planStageMove("lead", "lost")).toEqual({ kind: "lost" })
  })
  it("终态或阶段未变化时拒绝", () => {
    expect(planStageMove("won", "lead").kind).toBe("invalid")
    expect(planStageMove("lost", "lead").kind).toBe("invalid")
    expect(planStageMove("lead", "lead").kind).toBe("invalid")
  })
})

describe("canUndoStage", () => {
  it("只有非终态之间可撤销", () => {
    expect(canUndoStage("proposal", "lead")).toBe(true)
    expect(canUndoStage("won", "negotiation")).toBe(false)
    expect(canUndoStage("lost", "lead")).toBe(false)
    expect(canUndoStage("lead", "lead")).toBe(false)
  })
})

describe("提示文案", () => {
  it("切换 / 撤销提示带阶段中文名，撤销窗口 8 秒", () => {
    expect(stageChangedText("proposal")).toBe("已切换到「方案报价」")
    expect(stageUndoneText("lead")).toBe("已撤销，恢复为「线索」")
    expect(UNDO_DURATION_MS).toBe(8000)
  })
})

describe("确认文案", () => {
  it("只有赢单需要确认", () => {
    expect(stageNeedsConfirm("won")).toBe(true)
    expect(stageNeedsConfirm("proposal")).toBe(false)
    const c = stageConfirm("合同审查私有化")
    expect(c.title).toBe("标记为赢单")
    expect(c.confirmLabel).toBe("确认赢单")
    expect(c.description).toContain("不能再切换阶段")
  })
  it("报价：提交不需要确认，发送 / 接受 / 拒绝需要", () => {
    expect(quoteActionConfirm("submit")).toBeNull()
    expect(quoteActionConfirm("send")?.confirmLabel).toBe("确认发送")
    expect(quoteActionConfirm("accept")?.description).toContain("自动生成合同和提成")
    expect(quoteActionConfirm("reject")?.destructive).toBe(true)
  })
  it("审批通过 / 报销提交 / 登记回款", () => {
    expect(approveConfirm("Q-1", "quote").confirmLabel).toBe("确认通过")
    expect(approveConfirm("E-1", "expense").description).toContain("E-1")
    expect(expenseSubmitConfirm(false).description).toContain("不能再修改票据")
    // 回归：原来一律写「进入主管审批」，符合标准的其实直接通过
    expect(expenseSubmitConfirm(false).description).toContain("符合标准直接通过")
    expect(expenseSubmitConfirm(true).description).toContain("个人模式不用审批")
    expect(paymentConfirm("¥1,000", "C-1").description).toContain("¥1,000")
  })
})
