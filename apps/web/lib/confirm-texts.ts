/** 不可逆操作的确认文案（标题写动作、正文写后果、按钮「确认 xxx」），纯数据便于测试和复用 */
import { STAGE_META } from "@/lib/labels"
import type { OpportunityStage, QuoteAction } from "@/types/api"

export interface ConfirmCopy {
  title: string
  description: string
  confirmLabel: string
  destructive?: boolean
}

/** 切到终态「赢单」前确认；其余阶段可撤销，不需要确认（输单走原因弹窗） */
export function stageNeedsConfirm(to: OpportunityStage): boolean {
  return to === "won"
}

export function stageConfirm(name: string): ConfirmCopy {
  return {
    title: `标记为${STAGE_META.won.label}`,
    description: `「${name}」标记为赢单后为终态，不能再切换阶段，也不能撤销。`,
    confirmLabel: `确认${STAGE_META.won.label}`,
  }
}

/** 报价单动作：提交可由主管驳回退回，不需要确认；发送 / 接受 / 拒绝不可撤回 */
const QUOTE_CONFIRM: Partial<Record<QuoteAction, ConfirmCopy>> = {
  send: {
    title: "发送给客户",
    description: "发送后报价单状态变为「已发送客户」，不能再撤回或修改。",
    confirmLabel: "确认发送",
  },
  accept: {
    title: "标记为客户接受",
    description: "客户接受后将自动生成合同和提成，不能撤回。",
    confirmLabel: "确认客户接受",
  },
  reject: {
    title: "标记为客户拒绝",
    description: "标记客户拒绝后报价单为终态，不能撤回。",
    confirmLabel: "确认客户拒绝",
    destructive: true,
  },
}

export function quoteActionConfirm(action: QuoteAction): ConfirmCopy | null {
  return QUOTE_CONFIRM[action] ?? null
}

export function approveConfirm(code: string, targetType: "quote" | "expense"): ConfirmCopy {
  return {
    title: "通过审批",
    description:
      targetType === "quote"
        ? `报价单 ${code} 通过后销售即可发送客户，审批结果不能撤回。`
        : `报销 ${code} 通过后进入打款流程，审批结果不能撤回。`,
    confirmLabel: "确认通过",
  }
}

export const EXPENSE_SUBMIT_CONFIRM: ConfirmCopy = {
  title: "提交报销审批",
  description: "提交后进入主管审批，不能再修改票据或撤回。",
  confirmLabel: "确认提交",
}

export function paymentConfirm(amountText: string, code: string): ConfirmCopy {
  return {
    title: "登记回款",
    description: `将为合同 ${code} 登记回款 ${amountText}，并按回款比例确认提成，登记后不能撤回。`,
    confirmLabel: "确认登记",
  }
}
