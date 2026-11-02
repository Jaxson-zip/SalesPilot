/** 报价单：按当前状态计算可用操作（契约 §3 状态流转表），以及明细 → 物料清单的转换 */
import { formatFen, formatPercent } from "@/lib/format"
import type { BomData, QuoteAction, QuoteDetail, QuoteStatus } from "@/types/api"

export interface QuoteActionMeta {
  action: QuoteAction
  label: string
  /** 成功后的提示 */
  done: string
}

export const QUOTE_ACTIONS: Record<QuoteAction, QuoteActionMeta> = {
  submit: { action: "submit", label: "提交", done: "报价单已提交" },
  send: { action: "send", label: "发送客户", done: "报价单已发送客户" },
  accept: { action: "accept", label: "客户接受", done: "客户已接受，已生成合同与提成" },
  reject: { action: "reject", label: "客户拒绝", done: "已标记为客户拒绝" },
  renew: { action: "renew", label: "续期", done: "已退回草稿，确认价格后重新提交" },
}

/** 动作允许的当前状态（与 core 的 quote_status_transition 规则保持一致） */
const ALLOWED_FROM: Record<Exclude<QuoteAction, "renew">, QuoteStatus> = {
  submit: "draft",
  send: "approved",
  accept: "sent",
  reject: "sent",
}

/**
 * 返回当前状态可用的操作，顺序：次要在前、主要在后（页面最右侧是主按钮）。
 * 过了有效期（core 的 quote_expired）：不能再发送、客户接受，只剩续期（已发送的还能标客户拒绝）。
 */
export function availableQuoteActions(status: QuoteStatus, expired = false): QuoteAction[] {
  const order = ["reject", "accept", "submit", "send"] as const
  const list: QuoteAction[] = order.filter((a) => ALLOWED_FROM[a] === status)
  if (!expired || (status !== "approved" && status !== "sent")) return list
  return [...list.filter((a) => a === "reject"), "renew"]
}

/** 主按钮：可用操作中的最后一个 */
export function primaryQuoteAction(status: QuoteStatus, expired = false): QuoteAction | null {
  const list = availableQuoteActions(status, expired)
  return list.length ? list[list.length - 1] : null
}

/** submit 成功后根据返回状态给出不同提示 */
export function submitResultText(status: QuoteStatus): string {
  if (status === "approved") return "毛利达标，已自动通过，可以发送客户"
  if (status === "pending_approval") return "触发审批规则，已提交主管审批"
  return QUOTE_ACTIONS.submit.done
}

/** 报价明细 → 物料清单组件（BomTable）的数据 */
export function quoteToBom(
  q: Pick<
    QuoteDetail,
    "tier_name" | "items" | "total_cost" | "total_price" | "margin_rate" | "estimated_commission" | "client_costs"
  >,
): BomData {
  return {
    title: `${q.tier_name || "方案"} · 物料清单`,
    items: q.items.map((it) => ({
      name: it.name,
      quantity: `${it.qty} ${it.unit}`.trim(),
      cost: it.subtotal_cost,
      price: it.subtotal_price,
    })),
    totals: [
      { label: "成本合计", value: formatFen(q.total_cost) },
      { label: "报价合计", value: formatFen(q.total_price) },
      { label: "毛利率", value: formatPercent(q.margin_rate) },
      { label: "预估提成", value: formatFen(q.estimated_commission) },
    ],
    client_costs: q.client_costs ?? [],
  }
}
