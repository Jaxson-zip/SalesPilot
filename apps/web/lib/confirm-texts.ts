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
  renew: {
    title: "报价续期",
    description: "报价退回草稿：确认价格和范围后重新提交，有效期从今天重新算，需要审批的会重新审批。",
    confirmLabel: "退回草稿续期",
  },
  revise: {
    title: "撤回修改报价",
    description: "报价退回草稿，可以调整物料和价格；改完需要重新提交，触发审批规则的会重新审批。",
    confirmLabel: "撤回修改",
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

/**
 * 提交报销：符合标准的直接通过，超标的才进主管审批；个人模式不用审批（与 core expense_service 一致）。
 * 回归：原来一律写「提交后进入主管审批」，符合标准的报销其实直接通过了。
 */
export function expenseSubmitConfirm(solo: boolean): ConfirmCopy {
  const flow = solo
    ? "个人模式不用审批，提交后直接通过，超标的会记一条提醒。"
    : "提交后系统按报销制度校验：符合标准直接通过，超标的进入主管审批。"
  return { title: "提交报销", description: `${flow}提交后不能再修改票据或撤回。`, confirmLabel: "确认提交" }
}

/** 报价提交前的审批预判（个人模式没有主管，触发的规则只记提醒） */
export function quoteApprovalHint(reasons: string[], solo: boolean): string {
  if (!reasons.length) return "按现在的价格提交会自动通过，不用审批"
  return solo
    ? `个人模式不用审批，提交后直接通过，会记下提醒：${reasons.join("；")}`
    : `提交后要主管审批：${reasons.join("；")}`
}

/** 草稿报价上的审批规则说明 */
export function quoteDraftRule(solo: boolean): string {
  return solo
    ? "个人模式不用审批：提交后直接通过；毛利低于底线或折扣超权限时会记一条提醒。"
    : "毛利达标自动通过；低于底线或折扣超权限时进入主管审批。"
}

/** 报销超标提示的标题 */
export function expenseOverTitle(overAmount: number, solo: boolean): string {
  if (solo) return overAmount ? "超出报销标准（个人模式不用审批，会记下提醒）" : "制度里没有标准（个人模式不用审批）"
  return overAmount ? "超出报销标准，需主管审批" : "需主管审批"
}

export function paymentConfirm(amountText: string, code: string): ConfirmCopy {
  return {
    title: "登记回款",
    description: `将为合同 ${code} 登记回款 ${amountText}，并按回款比例确认提成。登记后不能修改，录错了只能由主管冲正（另记一笔负数并写明原因）。`,
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
    description:
      "已审批的报销单里仍保留这位参与人的名字；还在草稿、待审批或被驳回的报销单用到 TA 时不能删除。客户动态会记录这次删除。",
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

/** 新建 / 编辑表单有没保存的内容时关闭侧栏（Esc、点遮罩、点 ✕） */
export const DISCARD_FORM_CONFIRM: ConfirmCopy = {
  title: "放弃没保存的内容？",
  description: "关闭后这次填写的内容不会保留。",
  confirmLabel: "放弃并关闭",
  destructive: true,
}
