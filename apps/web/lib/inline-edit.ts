/** 行内编辑（U10）：输入框文字 → 接口值。金额输入元、传分；可清空的字段空串 → null */
import { fenToYuanInput, yuanToFen } from "@/lib/money"

export type InlineKind = "text" | "money" | "int" | "date" | "select"

export interface InlineSpec {
  kind: InlineKind
  /** 不能清空（名称、金额等） */
  required?: boolean
  min?: number
  max?: number
}

export type ParseResult = { ok: true; value: string | number | null } | { ok: false; error: string }

export function parseInline(raw: string, spec: InlineSpec): ParseResult {
  const text = raw.trim()
  if (!text) return spec.required ? { ok: false, error: "不能为空" } : { ok: true, value: null }
  if (spec.kind === "money") {
    const fen = yuanToFen(text)
    return fen === null || fen < 0 ? { ok: false, error: "请输入金额，最多两位小数" } : { ok: true, value: fen }
  }
  if (spec.kind === "int") {
    const n = Number(text)
    const { min = Number.MIN_SAFE_INTEGER, max = Number.MAX_SAFE_INTEGER } = spec
    if (!Number.isInteger(n) || n < min || n > max) return { ok: false, error: `请输入 ${min}–${max} 的整数` }
    return { ok: true, value: n }
  }
  return { ok: true, value: text }
}

/** 接口值 → 编辑框初始文字 */
export function toInlineText(value: string | number | null | undefined, kind: InlineKind): string {
  if (value === null || value === undefined) return ""
  return kind === "money" && typeof value === "number" ? fenToYuanInput(value) : String(value)
}
