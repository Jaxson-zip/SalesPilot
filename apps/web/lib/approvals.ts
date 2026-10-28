/**
 * 审批列表：筛选、排序、汇总（纯函数）。
 * 待处理的单子一次取回（最多 100 条），在前端按类型 / 关键词筛选、按金额或超标排序，数据多时不用一条条翻。
 */
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
  amount: number
  over: number
  byType: Record<ApprovalTargetType, number>
}

export function summarizeApprovals(items: ApprovalItem[]): ApprovalSummary {
  const byType: Record<ApprovalTargetType, number> = { expense: 0, quote: 0 }
  let amount = 0
  let over = 0
  for (const a of items) {
    byType[a.target_type] += 1
    amount += a.target.amount
    over += a.target.over_amount ?? 0
  }
  return { count: items.length, amount, over, byType }
}
