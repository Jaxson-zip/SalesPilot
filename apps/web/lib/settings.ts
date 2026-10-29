/**
 * 网页上维护的配置（GET/PUT /api/settings/rules、/api/packs/{id}/settings）：类型 + 输入框文字 ↔ 存储值的转换。
 * 存储单位：比例是小数（0.25）、金额是分、大小是字节；输入框里分别写 25、元、MB。
 */
import { formatFen } from "@/lib/format"

export type SettingKind =
  "percent" | "money" | "int" | "float" | "cities" | "percent_list" | "stages" | "megabytes" | "bool"

export interface PaymentStageValue {
  name: string
  /** 0–1 */
  ratio: number
  due_days: number
}

export interface SettingValue {
  key: string
  label: string
  group: string
  kind: SettingKind
  unit: string
  min: number | null
  max: number | null
  help: string
  value: unknown
  default: unknown
  overridden: boolean
  updated_at: string | null
  updated_by: string | null
}

export interface SettingsOut {
  groups: string[]
  fields: SettingValue[]
}

export interface SettingsUpdate {
  /** key → 新值；null = 恢复默认 */
  values: Record<string, unknown>
}

export interface CatalogEdit {
  name?: string | null
  unit?: string | null
  cost?: number | null
  price?: number | null
}

export interface KnowledgeUploadOut {
  doc_name: string
  chunks: number
}

const MB = 1024 * 1024
/** 去掉浮点误差：0.07 * 100 = 7.000000000000001 */
const tidy = (n: number) => Number(n.toPrecision(12))
const asNumber = (v: unknown) => (typeof v === "number" ? v : Number(v))

/** 只读展示：25% / ¥150 / 30 天 / 北京、上海 / 预付款 30%（签订当天）… */
export function formatSetting(kind: SettingKind, value: unknown, unit = ""): string {
  if (value === null || value === undefined) return "—"
  const u = unit ? ` ${unit}` : ""
  switch (kind) {
    case "bool":
      return value ? "开" : "关"
    case "percent":
      return `${tidy(asNumber(value) * 100)}%`
    case "money":
      return `${formatFen(asNumber(value))}${unit.startsWith("元") ? unit.slice(1) : u}`
    case "megabytes":
      return `${tidy(asNumber(value) / MB)} MB`
    case "cities":
      return Array.isArray(value) ? value.join("、") : String(value)
    case "percent_list":
      return Array.isArray(value) ? value.map((x) => `${tidy(asNumber(x) * 100)}%`).join(" → ") : String(value)
    case "stages":
      return Array.isArray(value)
        ? (value as PaymentStageValue[])
            .map((s) => `${s.name} ${tidy(s.ratio * 100)}%（${s.due_days === 0 ? "签订当天" : `${s.due_days} 天`}）`)
            .join("，")
        : String(value)
    default:
      return `${String(value)}${unit === "%" ? "%" : u}`
  }
}

/** 存储值 → 输入框文字（stages 用单独的表格编辑，不走这里） */
export function toInputText(kind: SettingKind, value: unknown): string {
  if (value === null || value === undefined) return ""
  switch (kind) {
    case "percent":
      return String(tidy(asNumber(value) * 100))
    case "money":
      return String(tidy(asNumber(value) / 100))
    case "megabytes":
      return String(tidy(asNumber(value) / MB))
    case "cities":
      return Array.isArray(value) ? value.join("、") : String(value)
    case "percent_list":
      return Array.isArray(value) ? value.map((x) => tidy(asNumber(x) * 100)).join("、") : String(value)
    default:
      return String(value)
  }
}

export type Parsed = { ok: true; value: unknown } | { ok: false; error: string }

const SPLIT = /[,，、\s]+/

function num(text: string): number | null {
  const t = text.trim()
  if (!t) return null
  const n = Number(t)
  return Number.isFinite(n) ? n : null
}

/** 输入框文字 → 存储值；范围用后端给的 min/max（按存储单位）先校验一遍，后端会再校验 */
export function parseInputText(field: Pick<SettingValue, "kind" | "min" | "max" | "label">, text: string): Parsed {
  const { kind, min, max, label } = field
  if (kind === "bool") return { ok: true, value: text === "true" }
  const inRange = (v: number) => (min === null || v >= min) && (max === null || v <= max)
  const range = () => {
    const fmt = (v: number) => formatSetting(kind === "percent_list" ? "percent" : kind, v)
    return `「${label}」要在 ${min === null ? "—" : fmt(min)} 到 ${max === null ? "—" : fmt(max)} 之间`
  }
  if (kind === "cities") {
    const cities = [
      ...new Set(
        text
          .split(SPLIT)
          .map((s) => s.trim())
          .filter(Boolean),
      ),
    ]
    return cities.length ? { ok: true, value: cities } : { ok: false, error: `「${label}」至少要有一个城市` }
  }
  if (kind === "percent_list") {
    const parts = text.split(SPLIT).filter(Boolean)
    const values = parts.map((p) => num(p))
    if (!parts.length || values.some((v) => v === null))
      return { ok: false, error: `「${label}」请用顿号分隔数字，例如 8、4、0` }
    const ratios = values.map((v) => tidy((v as number) / 100))
    return ratios.every(inRange) ? { ok: true, value: ratios } : { ok: false, error: range() }
  }
  const n = num(text)
  if (n === null) return { ok: false, error: `「${label}」请填写数字` }
  let value: number
  if (kind === "percent") value = tidy(n / 100)
  else if (kind === "money") value = Math.round(n * 100)
  else if (kind === "megabytes") value = Math.round(n * MB)
  else value = n
  if ((kind === "int" || kind === "megabytes") && !Number.isInteger(kind === "megabytes" ? n : value))
    return { ok: false, error: `「${label}」请填写整数` }
  const scaled = kind === "megabytes" ? value / MB : value
  return inRange(scaled) ? { ok: true, value } : { ok: false, error: range() }
}

/** 回款计划校验：名称必填、比例合计 100% */
export function validateStages(stages: PaymentStageValue[]): string | null {
  if (stages.length === 0 || stages.length > 6) return "回款计划需要 1–6 期"
  if (stages.some((s) => !s.name.trim())) return "每一期都要有名称"
  if (stages.some((s) => !(s.ratio > 0 && s.ratio <= 1))) return "每一期的比例要在 0–100% 之间"
  if (stages.some((s) => !Number.isInteger(s.due_days) || s.due_days < 0)) return "到期天数要是非负整数"
  const total = Math.round(stages.reduce((n, s) => n + s.ratio, 0) * 10000) / 100
  return total === 100 ? null : `各期比例合计 ${total}%，必须是 100%`
}

export const CATEGORY_LABEL: Record<string, string> = { hardware: "硬件", software: "软件", service: "服务" }
