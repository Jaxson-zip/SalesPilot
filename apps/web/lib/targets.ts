/** 业绩目标（契约 §27）：月份切换、完成进度与时间进度对比、目标输入换算 */
import { formatFen } from "@/lib/format"
import type { Role } from "@/types/api"

export interface TargetRow {
  user: { id: string; name: string }
  role: Role
  team_name: string | null
  active: boolean
  /** 签约额目标（分）；没设为 null */
  target: number | null
  /** 当月新签合同金额（分） */
  achieved: number
  contracts: number
  /** 预计当月成交的进行中商机，金额 × 赢率 */
  forecast: number
  rate: number | null
}

export interface TargetBoard {
  month: string
  editable: boolean
  /** 当月时间进度 0～1 */
  time_progress: number
  total: { target: number | null; achieved: number; forecast: number; rate: number | null }
  rows: TargetRow[]
}

export interface TargetUpdate {
  items: { user_id: string; amount: number | null }[]
}

/** "2026-10" 前后移动 n 个月 */
export function shiftMonth(month: string, n: number): string {
  const [y, m] = month.split("-").map(Number)
  const d = new Date(y, m - 1 + n, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
}

export function monthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number)
  return `${y} 年 ${m} 月`
}

export type Pace = "done" | "ahead" | "behind" | "none"

/** 完成率和时间进度比：达标、领先（不低于时间进度）、落后 */
export function pace(rate: number | null, timeProgress: number): Pace {
  if (rate === null) return "none"
  if (rate >= 1) return "done"
  return rate >= timeProgress ? "ahead" : "behind"
}

export const PACE_LABEL: Record<Pace, string> = {
  done: "已达标",
  ahead: "进度正常",
  behind: "落后于时间进度",
  none: "未设目标",
}

/** 还差多少：「还差 ¥12,000」「超出 ¥3,000」；没目标为空 */
export function gapText(target: number | null, achieved: number): string {
  if (!target) return ""
  const gap = target - achieved
  return gap > 0 ? `还差 ${formatFen(gap)}` : `超出 ${formatFen(-gap)}`
}

/** 输入框里填的是「万元」：「50」「12.5」→ 分；空串为 null（清除）；不合法为 undefined */
export function parseWan(text: string): number | null | undefined {
  const t = text.trim()
  if (!t) return null
  if (!/^\d+(\.\d{1,4})?$/.test(t)) return undefined
  const fen = Math.round(Number(t) * 1_000_000)
  return fen <= 1e13 ? fen : undefined
}

export function toWan(fen: number | null): string {
  if (fen === null) return ""
  return String(Number((fen / 1_000_000).toFixed(4)))
}

/** 只提交改过的人 */
export function changedItems(rows: TargetRow[], drafts: Record<string, string>): TargetUpdate["items"] {
  const out: TargetUpdate["items"] = []
  for (const r of rows) {
    const text = drafts[r.user.id]
    if (text === undefined) continue
    const amount = parseWan(text)
    if (amount === undefined || amount === r.target) continue
    out.push({ user_id: r.user.id, amount })
  }
  return out
}
