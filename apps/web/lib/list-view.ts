/**
 * 列表页 ViewBar 的纯函数：筛选、排序、筛选标签、CSV 导出、显示字段偏好。
 * 客户 / 报价 / 合同 / 报销在服务端筛选、排序、分页（FilterDef.param）；
 * 商机看板要全部卡片，取全后在前端筛选（FilterDef.get）。
 */

export interface FilterOption {
  value: string
  label: string
}

export interface FilterDef<T> {
  id: string
  label: string
  options: FilterOption[]
  /** 前端筛选：行 → 该字段的值（与 options.value 对应）；null 表示空 */
  get?: (row: T) => string | null
  /** 服务端筛选：查询参数名（默认同 id），选中的值作为重复参数发送 */
  param?: string
}

/** 服务端列表的筛选 / 排序参数（拼进列表接口的查询参数） */
export interface ServerListParams {
  sort?: SortKey
  filters?: Record<string, string[]>
}

/** 生效筛选 → 查询参数 { 参数名: 选中值[] } */
export function filterParams<T>(defs: FilterDef<T>[], active: ActiveFilters): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const d of defs) {
    const values = active[d.id]
    if (values?.length) out[d.param ?? d.id] = values
  }
  return out
}

/** 列表接口的查询参数：排序 + 筛选（默认排序不发送） */
export function serverQuery(p: ServerListParams): Record<string, string | string[] | undefined> {
  return { sort: p.sort && p.sort !== "default" ? p.sort : undefined, ...p.filters }
}

/** 生效的筛选：字段 id → 选中的值（同一字段内为「或」，不同字段之间为「且」） */
export type ActiveFilters = Record<string, string[]>

export function applyFilters<T>(rows: T[], defs: FilterDef<T>[], active: ActiveFilters): T[] {
  const live = defs.filter((d) => d.get && (active[d.id]?.length ?? 0) > 0)
  if (live.length === 0) return rows
  return rows.filter((r) =>
    live.every((d) => {
      const v = d.get?.(r) ?? null
      return v !== null && active[d.id].includes(v)
    }),
  )
}

/** 勾选 / 取消某个筛选值（返回新对象；字段没有选中值时删除该键） */
export function toggleFilter(active: ActiveFilters, id: string, value: string): ActiveFilters {
  const cur = active[id] ?? []
  const nextVals = cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value]
  const next = { ...active }
  if (nextVals.length) next[id] = nextVals
  else delete next[id]
  return next
}

export interface FilterChip {
  id: string
  value: string
  label: string
}

/** 生效筛选 → 可清除的标签（「状态：草稿」） */
export function filterChips<T>(defs: FilterDef<T>[], active: ActiveFilters): FilterChip[] {
  return defs.flatMap((d) =>
    (active[d.id] ?? []).map((value) => ({
      id: d.id,
      value,
      label: `${d.label}：${d.options.find((o) => o.value === value)?.label ?? value}`,
    })),
  )
}

/** 从已加载数据里收集选项（例如客户「行业」没有固定枚举），去重并按出现顺序 */
export function optionsFromRows<T>(rows: T[], get: (row: T) => string | null | undefined): FilterOption[] {
  const seen = new Set<string>()
  const out: FilterOption[] = []
  for (const r of rows) {
    const v = get(r)
    if (v && !seen.has(v)) {
      seen.add(v)
      out.push({ value: v, label: v })
    }
  }
  return out
}

export type SortKey = "default" | "updated" | "amount_desc" | "amount_asc"

export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "default", label: "默认顺序" },
  { value: "updated", label: "最近更新" },
  { value: "amount_desc", label: "金额从高到低" },
  { value: "amount_asc", label: "金额从低到高" },
]

export interface SortAccessors<T> {
  /** ISO 时间；null 排在最后 */
  updated: (row: T) => string | null
  /** 金额（分） */
  amount: (row: T) => number
}

const time = (iso: string | null): number => {
  const t = iso ? Date.parse(iso) : NaN
  return Number.isNaN(t) ? -Infinity : t
}

/** 对当前页数据排序（稳定排序，返回新数组） */
export function sortRows<T>(rows: T[], key: SortKey, acc: SortAccessors<T>): T[] {
  if (key === "default") return rows
  const indexed = rows.map((r, i) => ({ r, i }))
  indexed.sort((a, b) => {
    let d = 0
    if (key === "updated") d = time(acc.updated(b.r)) - time(acc.updated(a.r))
    else if (key === "amount_desc") d = acc.amount(b.r) - acc.amount(a.r)
    else d = acc.amount(a.r) - acc.amount(b.r)
    return d === 0 || Number.isNaN(d) ? a.i - b.i : d
  })
  return indexed.map((x) => x.r)
}

/** 分 → 元（两位小数，不带千分位，便于 Excel 计算） */
export function fenToYuan(fen: number | null | undefined): string {
  if (fen === null || fen === undefined || Number.isNaN(fen)) return ""
  const sign = fen < 0 ? "-" : ""
  const abs = Math.abs(Math.round(fen))
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`
}

export interface CsvColumn<T> {
  label: string
  value: (row: T) => string | number | null | undefined
}

/** 以 = + @ 制表符 回车 开头、或 - 后面不是数字的文字，Excel 会当公式执行（CSV 注入）：前面加 ' 当文本 */
const FORMULA = /^(?:[=+@\t\r]|-(?![\d.]))/

function csvCell(v: string | number | null | undefined): string {
  const raw = v === null || v === undefined ? "" : String(v)
  const s = typeof v === "string" && FORMULA.test(raw) ? `'${raw}` : raw
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/** 生成 CSV 文本：UTF-8 BOM（Excel 直接打开不乱码）+ CRLF 换行 + RFC 4180 转义 */
export function toCsv<T>(columns: CsvColumn<T>[], rows: T[]): string {
  const lines = [columns.map((c) => csvCell(c.label)).join(",")]
  for (const r of rows) lines.push(columns.map((c) => csvCell(c.value(r))).join(","))
  return `﻿${lines.join("\r\n")}\r\n`
}

/** localStorage 里的隐藏列（JSON 字符串数组）；格式不对时当作没有偏好 */
export function parseHiddenColumns(raw: string | null): string[] {
  if (!raw) return []
  try {
    const v: unknown = JSON.parse(raw)
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []
  } catch {
    return []
  }
}

export function toggleHidden(hidden: string[], id: string): string[] {
  return hidden.includes(id) ? hidden.filter((h) => h !== id) : [...hidden, id]
}
