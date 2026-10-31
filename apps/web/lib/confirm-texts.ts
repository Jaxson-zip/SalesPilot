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

/** 主管批量转移客户负责人（v3 §16）：未选目标时只说明范围 */
export function transferConfirm(count: number, toName: string | null): ConfirmCopy {
  const scope = "客户及其未结束的商机、未完成的任务、未成交的报价"
  return {
    title: "转移负责人",
    description: toName
      ? `将选中的 ${count} 个${scope}一起转移给「${toName}」，并通知新负责人。`
      : `请选择本团队的新负责人。选中的 ${count} 个${scope}会一起转移。`,
    confirmLabel: "确认转移",
  }
}

/** 按人交接的影响范围：「3 个客户、2 个进行中的商机、1 份回款中的合同」，没有的项不写 */
export function handoverSummary(r: {
  customers: number
  opportunities: number
  tasks: number
  quotes: number
  contracts: number
}): string {
  const parts: [number, string][] = [
    [r.customers, "个客户"],
    [r.opportunities, "个进行中的商机"],
    [r.quotes, "份未成交的报价"],
    [r.tasks, "个未完成的任务"],
    [r.contracts, "份回款中的合同"],
  ]
  return parts
    .filter(([n]) => n > 0)
    .map(([n, unit]) => `${n} ${unit}`)
    .join("、")
}

export function deleteCompetitorConfirm(name: string): ConfirmCopy {
  return {
    title: `删除「${name}」战卡？`,
    description: "已标注这个竞品的商机会移除标注；历史输赢战绩不再显示。",
    confirmLabel: "确认删除",
    destructive: true,
  }
}

export const REDRAFT_REPORT_CONFIRM: ConfirmCopy = {
  title: "重新生成日报草稿？",
  description: "AI 会按今天的操作重新写一版，覆盖输入框里的当前内容（已提交的版本不受影响，直到你再次提交）。",
  confirmLabel: "覆盖并生成",
}

export function deleteContactConfirm(name: string): ConfirmCopy {
  return {
    title: `删除联系人「${name}」？`,
    description: "删除后，历史报销单里的参与人记录不受影响；客户动态会记录这次删除。",
    confirmLabel: "确认删除",
    destructive: true,
  }
}

/** 日报有没保存的修改时离开页面 */
export const LEAVE_REPORT_CONFIRM: ConfirmCopy = {
  title: "日报还没保存",
  description: "离开后这次的修改不会提交（会暂存在这台电脑的浏览器里，回来时恢复）。建议先点「保存草稿」。",
  confirmLabel: "先离开",
}
