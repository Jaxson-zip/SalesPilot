/**
 * 审批列表：筛选、排序、汇总（纯函数）。
 * 待处理的单子一次取回（最多 100 条），在前端按类型 / 关键词筛选、按金额或超标排序，数据多时不用一条条翻。
 */
import { formatFen } from "@/lib/format"
import type { ApprovalItem, ApprovalTargetType } from "@/types/api"

export type ApprovalSort = "oldest" | "amount" | "over"
export type ApprovalTypeFilter = "all" | ApprovalTargetType

export const APPROVAL_SORT_LABEL: Record<ApprovalSort, string> = {
  oldest: "最早提交优先",
  amount: "金额从高到低",
  over: "超标最多优先",
}

export function filterApprovals(items: ApprovalItem[], type: ApprovalTypeFilter, q: string): ApprovalItem[] {
  const kw = q.trim().toLowerCase()
  return items.filter((a) => {
    if (type !== "all" && a.target_type !== type) return false
    if (!kw) return true
    const t = a.target
    return [t.code, t.title, t.owner?.name ?? "", a.reason].some((s) => s.toLowerCase().includes(kw))
  })
}

const time = (a: ApprovalItem) => Date.parse(a.created_at) || 0

export function sortApprovals(items: ApprovalItem[], sort: ApprovalSort): ApprovalItem[] {
  const out = items.slice()
  if (sort === "amount") out.sort((a, b) => b.target.amount - a.target.amount || time(a) - time(b))
  else if (sort === "over")
    out.sort((a, b) => (b.target.over_amount ?? 0) - (a.target.over_amount ?? 0) || time(a) - time(b))
  else out.sort((a, b) => time(a) - time(b))
  return out
}

export interface ApprovalSummary {
  count: number
  /** 金额按类型分开：报价金额和报销金额含义不同，不加在一起 */
  amountByType: Record<ApprovalTargetType, number>
  over: number
  byType: Record<ApprovalTargetType, number>
}

export function summarizeApprovals(items: ApprovalItem[]): ApprovalSummary {
  const byType: Record<ApprovalTargetType, number> = { expense: 0, quote: 0 }
  const amountByType: Record<ApprovalTargetType, number> = { expense: 0, quote: 0 }
  let over = 0
  for (const a of items) {
    byType[a.target_type] += 1
    amountByType[a.target_type] += a.target.amount
    over += a.target.over_amount ?? 0
  }
  return { count: items.length, amountByType, over, byType }
}

/** 「报价 ¥298,000 · 报销 ¥860」：只列有单子的类型 */
export function approvalAmountText(s: ApprovalSummary): string {
  const parts: string[] = []
  if (s.byType.quote) parts.push(`报价 ${formatFen(s.amountByType.quote)}`)
  if (s.byType.expense) parts.push(`报销 ${formatFen(s.amountByType.expense)}`)
  return parts.join(" · ")
}

/**
 * 报价详情上主管「去审批」要定位的审批 id：只有主管、报价待审批、且有待处理的审批记录时才有。
 * 跳到审批列表那一条处理，通过 / 驳回的确认和必填原因都沿用审批页。
 */
export function pendingApprovalId(
  q: { status: string; approvals: { id: string; status: string }[] },
  canApprove: boolean,
): string | null {
  if (!canApprove || q.status !== "pending_approval") return null
  return q.approvals.find((a) => a.status === "pending")?.id ?? null
}

/**
 * 工作台「审批」卡片点进去的地方：主管 → 审批中心（待我审批）；
 * 销售 / 管理员 → 待审批的报价或报销列表（只有报销在审时去报销，否则去报价）；没有待审批时不跳转。
 */
export function pendingCardHref(
  role: string,
  d: { pending_approvals: number; pending_quotes?: number; pending_expenses?: number } | undefined,
): string | undefined {
  if (!d?.pending_approvals) return role === "manager" ? "/approvals" : undefined
  if (role === "manager") return "/approvals"
  const onlyExpenses = !d.pending_quotes && Boolean(d.pending_expenses)
  return onlyExpenses ? "/expenses?view=pending_approval" : "/quotes?view=pending_approval"
}

/** 卡片下面一行：分开写报价和报销各几张，不混在一起 */
export function pendingCardHint(
  role: string,
  d: { pending_quotes?: number; pending_expenses?: number } | undefined,
): string {
  const lead = role === "manager" ? "需要你处理" : role === "admin" ? "等待各团队主管处理" : "你提交、等待主管审批"
  if (!d || (d.pending_quotes === undefined && d.pending_expenses === undefined)) return lead
  return `${lead}：报价 ${d.pending_quotes ?? 0} · 报销 ${d.pending_expenses ?? 0}`
}
