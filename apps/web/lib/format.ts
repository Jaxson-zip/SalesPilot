/** 金额（分）→ ¥372,000 / ¥1,234.50（规则 10：后端传分，前端格式化） */
export function formatFen(fen: number | null | undefined): string {
  if (fen === null || fen === undefined || Number.isNaN(fen)) return "—"
  const hasCents = fen % 100 !== 0
  return `¥${(fen / 100).toLocaleString("zh-CN", {
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
