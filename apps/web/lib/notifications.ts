/** 站内通知（契约 v3 §15）的纯函数：类型文案、未读角标、跳转链接 */
import type { NotificationItem } from "@/types/api"

export type NotificationTone = "approval" | "result" | "assign" | "task" | "other"

const META: Record<string, { label: string; tone: NotificationTone }> = {
  approval_pending: { label: "待审批", tone: "approval" },
  approval_decided: { label: "审批结果", tone: "result" },
  approval_remind: { label: "催办", tone: "approval" },
  invoice_requested: { label: "开票申请", tone: "approval" },
  invoice_issued: { label: "已开票", tone: "result" },
  invoice_voided: { label: "发票作废", tone: "result" },
  customer_assigned: { label: "客户转移", tone: "assign" },
  customer_handover: { label: "客户交接", tone: "assign" },
  account_deactivated: { label: "成员停用", tone: "assign" },
  task_due: { label: "任务到期", tone: "task" },
}

export function notificationMeta(type: string): { label: string; tone: NotificationTone } {
  return META[type] ?? { label: "通知", tone: "other" }
}

/** 铃铛红点上的数字：0 不显示，超过 99 显示 99+ */
export function unreadBadge(unread: number | undefined): string {
  if (!unread || unread <= 0) return ""
  return unread > 99 ? "99+" : String(unread)
}

/** 只跳转站内路由（以单个 / 开头），外链或空值返回 null，避免通知内容把用户带到站外 */
export function notificationHref(link: string | null | undefined): string | null {
  if (!link) return null
  const s = link.trim()
  if (!s.startsWith("/") || s.startsWith("//") || s.startsWith("/\\")) return null
  return s
}

/** 铃铛的 aria-label：「通知，3 条未读」 */
export function bellLabel(unread: number | undefined): string {
  return unread ? `通知，${unread} 条未读` : "通知"
}

/** 点击后本地立即标记已读（乐观更新），返回新列表 */
export function markReadLocally<T extends Pick<NotificationItem, "id" | "read">>(
  items: T[],
  ids?: string[],
): { items: T[]; changed: number } {
  let changed = 0
  const next = items.map((n) => {
    if (n.read || (ids && !ids.includes(n.id))) return n
    changed += 1
    return { ...n, read: true }
  })
  return { items: next, changed }
}
