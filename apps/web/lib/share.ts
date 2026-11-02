/** 报价分享链接（契约 §35）的纯函数：能否分享、完整链接、发给客户的话 */

/** 审批通过后才能分享（已审批的生成链接时会记为「已发送客户」） */
export const SHAREABLE_STATUSES = ["approved", "sent", "accepted"] as const

export function canShareQuote(status: string, expired = false): boolean {
  return !expired && (SHAREABLE_STATUSES as readonly string[]).includes(status)
}

/** 后端只给路径（/share/q/xxx），按当前打开的域名拼成完整链接 */
export function shareUrl(origin: string, path: string): string {
  return `${origin.replace(/\/+$/, "")}${path.startsWith("/") ? path : `/${path}`}`
}

/** 复制给客户的一段话（微信 / 邮件直接粘贴） */
export function shareMessage(
  q: { code: string; customer?: string | null; project?: string | null; validUntil?: string | null },
  url: string,
): string {
  const who = q.customer ? `${q.customer}您好` : "您好"
  const until = q.validUntil ? `，有效期至 ${q.validUntil.slice(0, 10)}` : ""
  const what = q.project ? `「${q.project}」的报价（${q.code}）` : `报价单 ${q.code}`
  return `${who}，${what}已经整理好，手机上可以直接打开查看${until}：\n${url}\n有任何调整随时告诉我。`
}

/** 报价链接被打开过几次的说明 */
export function viewSummary(count: number, lastViewedAt: string | null, relative: (iso: string) => string): string {
  if (count <= 0 || !lastViewedAt) return "客户还没有打开过"
  return `客户打开过 ${count} 次，最近一次 ${relative(lastViewedAt)}`
}
