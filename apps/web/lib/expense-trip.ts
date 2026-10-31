/**
 * 差旅报销的补充信息（v4）：交通填行程，住宿填城市和入住 / 离店日期。
 * 与后端 app/crm/services/expense_details.py 同一套规则；是否超标仍以后端校验为准。
 */
import { formatFen, localDate } from "@/lib/format"
import { yuanToFen } from "@/lib/money"
import type { ExpenseDetails, ExpenseTemplate, ExpenseType, TransportMode } from "@/types/api"

export interface TripValues {
  from_city: string
  to_city: string
  transport_mode: TransportMode | ""
  city: string
  /** YYYY-MM-DD */
  check_in: string
  check_out: string
}

export type TripErrors = Partial<Record<keyof TripValues, string>>

export const EMPTY_TRIP: TripValues = {
  from_city: "",
  to_city: "",
  transport_mode: "",
  city: "",
  check_in: "",
  check_out: "",
}

export const MAX_NIGHTS = 60

export const TRANSPORT_MODE_OPTIONS: { value: TransportMode; label: string }[] = [
  { value: "train", label: "高铁 / 火车" },
  { value: "flight", label: "飞机" },
  { value: "taxi", label: "出租车 / 网约车" },
  { value: "bus", label: "公交 / 地铁" },
  { value: "self_drive", label: "自驾" },
  { value: "other", label: "其他" },
]

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

/** 入住到离店的晚数；日期缺失或离店不晚于入住时为 0 */
export function nightsBetween(checkIn: string, checkOut: string): number {
  if (!DATE_RE.test(checkIn) || !DATE_RE.test(checkOut)) return 0
  const days = (Date.parse(`${checkOut}T00:00:00Z`) - Date.parse(`${checkIn}T00:00:00Z`)) / 86_400_000
  return days > 0 ? Math.round(days) : 0
}

/** 住宿必填城市和日期；交通都是选填 */
export function tripErrors(type: ExpenseType, t: TripValues): TripErrors {
  if (type !== "hotel") return {}
  const errors: TripErrors = {}
  if (!t.city.trim()) errors.city = "请填写住宿城市"
  if (!DATE_RE.test(t.check_in)) errors.check_in = "请选择入住日期"
  if (!DATE_RE.test(t.check_out)) errors.check_out = "请选择离店日期"
  else if (!errors.check_in) {
    const nights = nightsBetween(t.check_in, t.check_out)
    if (nights < 1) errors.check_out = "离店日期要晚于入住日期"
    else if (nights > MAX_NIGHTS) errors.check_out = `单张报销最多 ${MAX_NIGHTS} 晚，请分开报销`
    else if (t.check_out > localDate()) errors.check_out = "离店日期不能晚于今天，住完再报销"
  }
  return errors
}

/** 表单 → 请求体 details；不需要的类型返回 undefined */
export function toDetails(type: ExpenseType, t: TripValues): ExpenseDetails | undefined {
  if (type === "hotel") return { city: t.city.trim(), check_in: t.check_in, check_out: t.check_out }
  if (type !== "transport") return undefined
  const d: ExpenseDetails = {}
  if (t.from_city.trim()) d.from_city = t.from_city.trim()
  if (t.to_city.trim()) d.to_city = t.to_city.trim()
  if (t.transport_mode) d.transport_mode = t.transport_mode
  return Object.keys(d).length > 0 ? d : undefined
}

/** 住宿表单上的「共 2 晚，每晚 ¥600」；金额或日期不全时尽量给出已知部分 */
export function hotelSummary(amountYuan: string, t: Pick<TripValues, "check_in" | "check_out">): string | null {
  const nights = nightsBetween(t.check_in, t.check_out)
  if (nights < 1) return null
  const fen = yuanToFen(amountYuan)
  if (fen === null || fen <= 0) return `共 ${nights} 晚`
  return `共 ${nights} 晚，每晚 ${formatFen(Math.round(fen / nights))}`
}

/** 详情页的行程摘要：住宿「北京 · 2 晚（2026-10-01 至 2026-10-03）」，交通「深圳 → 北京 · 高铁 / 火车」 */
export function tripText(d: ExpenseDetails | null | undefined): string | null {
  if (!d) return null
  if (d.city) {
    const nights = nightsBetween(d.check_in ?? "", d.check_out ?? "")
    return nights ? `${d.city} · ${nights} 晚（${d.check_in} 至 ${d.check_out}）` : d.city
  }
  const route = [d.from_city, d.to_city].filter(Boolean).join(" → ")
  const mode = TRANSPORT_MODE_OPTIONS.find((m) => m.value === d.transport_mode)?.label
  return [route, mode].filter(Boolean).join(" · ") || null
}

/**
 * 选中模板：带出类型、交通方式和事由开头。
 * 事由只在为空或仍是某个模板的开头时替换，不覆盖用户已经写的内容。
 */
export function applyTemplate<V extends { type: ExpenseType; reason: string; trip: TripValues }>(
  values: V,
  tpl: ExpenseTemplate,
  allTemplates: ExpenseTemplate[],
): V {
  const untouched = !values.reason.trim() || allTemplates.some((t) => t.reason && values.reason === t.reason)
  return {
    ...values,
    type: tpl.type,
    reason: untouched ? tpl.reason : values.reason,
    trip: { ...values.trip, transport_mode: tpl.transport_mode ?? values.trip.transport_mode },
  }
}
