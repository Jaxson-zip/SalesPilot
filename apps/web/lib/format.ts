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

/** 北京时间比 UTC 快 8 小时（没有夏令时） */
const BEIJING_MS = 8 * 3_600_000
const DAY_MS = 86_400_000

/** 某个时刻在北京时间的钟面：用 getUTC* 读取年月日时分 */
function beijing(d: Date): Date {
  return new Date(d.getTime() + BEIJING_MS)
}

/**
 * 业务日期 YYYY-MM-DD：一律按北京时间（后端按北京时间算「今天」、逾期和日报日期）。
 * 回归：原来取浏览器所在时区的日期，在海外时区（如太平洋时间）每天傍晚以后和后端差一天，
 * 日报页查的是昨天、今天新建的报价和推进都显示 0。不能用 toISOString（那是 UTC）。
 */
export function localDate(d: Date = new Date()): string {
  const b = beijing(d)
  return `${b.getUTCFullYear()}-${pad(b.getUTCMonth() + 1)}-${pad(b.getUTCDate())}`
}

/** 北京时间的钟点 HH:mm */
export function localClock(d: Date): string {
  const b = beijing(d)
  return `${pad(b.getUTCHours())}:${pad(b.getUTCMinutes())}`
}

/** 业务日期 + n 天（纯日期运算，不受浏览器时区影响） */
export function addDays(date: string, n: number): string {
  const [y, m, d] = date.split("-").map(Number)
  return localDate(new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, (d ?? 1) + n) - BEIJING_MS))
}

/** 两个业务日期相差的天数（b - a） */
export function daysBetween(a: string, b: string): number {
  return Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / DAY_MS)
}

/** 业务日期 + 北京时间钟点 → 时刻；格式不对返回 null */
export function beijingInstant(date: string, time: string): Date | null {
  const d = new Date(`${date}T${time}+08:00`)
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * 跟进的发生时间：选的是今天就不传（后端记为保存时间）；补记往日的跟进取那天北京时间的此刻（带时区）。
 * 回归：原来拼成「YYYY-MM-DDT00:00:00」（不带时区），后端按 UTC 零点存，刚保存的跟进显示「15 小时前」。
 */
export function followupOccurredAt(date: string, now: Date = new Date()): string | undefined {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || date === localDate(now)) return undefined
  const b = beijing(now)
  return beijingInstant(date, `${localClock(now)}:${pad(b.getUTCSeconds())}`)?.toISOString()
}

/** 负责人显示名；没有负责人（公海客户、负责人账号已删除）时显示「未分配」 */
export function ownerName(owner: { name: string } | null | undefined): string {
  return owner?.name ?? "未分配"
}
