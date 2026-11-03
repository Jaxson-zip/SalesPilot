/** 金额（分）→ ¥372,000 / ¥1,234.50（规则 10：后端传分，前端格式化） */
export function formatFen(fen: number | null | undefined): string {
  if (fen === null || fen === undefined || Number.isNaN(fen)) return "—"
  const hasCents = fen % 100 !== 0
  // 负数（冲正记录）写成 -¥100 而不是 ¥-100
  return `${fen < 0 ? "-" : ""}¥${(Math.abs(fen) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: hasCents ? 2 : 0,
    maximumFractionDigits: 2,
  })}`
}

export function formatPercent(ratio: number, digits = 1): string {
  return `${(ratio * 100).toFixed(digits)}%`
}

const pad = (n: number): string => String(n).padStart(2, "0")

/** 相对时间：刚刚 / N 分钟前 / N 小时前 / 昨天 / MM-DD / YYYY-MM-DD */
export function formatRelative(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "—"
  const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000)
  if (diffMin < 1) return "刚刚"
  if (diffMin < 60) return `${diffMin} 分钟前`
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  if (d.getTime() >= startOfToday) return `${Math.floor(diffMin / 60)} 小时前`
  if (d.getTime() >= startOfToday - 86400000) return "昨天"
  if (d.getFullYear() === now.getFullYear()) return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 网址去掉协议和末尾斜杠，用于 LinkChip 显示 */
export function displayHost(url: string | null | undefined): string {
  if (!url) return ""
  return url.replace(/^https?:\/\//, "").replace(/\/$/, "")
}

/** 本地日期 YYYY-MM-DD（不能用 toISOString：那是 UTC，东八区凌晨会差一天） */
export function localDate(d: Date = new Date()): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/**
 * 跟进的发生时间：选的是今天就不传（后端记为保存时间）；补记往日的跟进取那天的此刻（带时区）。
 * 回归：原来拼成「YYYY-MM-DDT00:00:00」（不带时区），后端按 UTC 零点存，刚保存的跟进显示「15 小时前」。
 */
export function followupOccurredAt(date: string, now: Date = new Date()): string | undefined {
  if (!date || date === localDate(now)) return undefined
  const [y, m, d] = date.split("-").map(Number)
  const at = new Date(now)
  at.setFullYear(y ?? now.getFullYear(), (m ?? 1) - 1, d ?? 1)
  return Number.isNaN(at.getTime()) ? undefined : at.toISOString()
}

/** 负责人显示名；没有负责人（公海客户、负责人账号已删除）时显示「未分配」 */
export function ownerName(owner: { name: string } | null | undefined): string {
  return owner?.name ?? "未分配"
}
