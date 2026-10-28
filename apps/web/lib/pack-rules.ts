/**
 * 行业包详情（GET /api/packs/{pack_id}）的类型，以及业务规则（rules.yaml）→ 中文说明的纯函数。
 * 数值只做展示格式化（比例 → %，分 → 元），不参与任何计算。
 */
import { formatFen } from "@/lib/format"

export interface PackCatalogItem {
  sku: string
  name: string
  category: string
  unit: string
  /** 分 */
  cost: number
  /** 分 */
  price: number
  specs: Record<string, unknown> | string | null
  /** catalog.json 里的默认成本 / 售价（分）；管理员改过价格时与 cost / price 不同 */
  default_cost?: number
  default_price?: number
  /** 是否在网页上改过 */
  overridden?: boolean
}

export interface PackKnowledgeDoc {
  doc_name: string
  title: string
  /** 字节 */
  size: number
  /** 扩展名（不含点）：md / pdf / xlsx / json … */
  format?: string
  /** 是否进入知识库（RAG 支持的格式）；其他文件是行业包的配置数据 */
  indexed?: boolean
  /** builtin：随代码发布（不能在网页删除）；uploaded：网页上传 */
  source?: "builtin" | "uploaded"
  /** 已入库的切块数 */
  chunks?: number | null
}

export interface PackDetail {
  id: string
  name: string
  description: string
  version: string
  catalog: PackCatalogItem[]
  rules: Record<string, unknown>
  knowledge: PackKnowledgeDoc[]
}

type Fmt = "percent" | "fen" | "bytes" | "times" | "plain" | "days" | "years" | "tokens"

/** 已知规则键（点分路径）→ 中文说明 + 展示格式 */
const RULE_LABELS: Record<string, [string, Fmt]> = {
  "margin.floor_rate": ["毛利底线（低于需主管审批）", "percent"],
  "discount.max_rate": ["销售折扣权限上限", "percent"],
  "commission.rates.hardware": ["提成比例 · 硬件", "percent"],
  "commission.rates.software": ["提成比例 · 软件", "percent"],
  "commission.rates.service": ["提成比例 · 服务", "percent"],
  "commission.low_margin_floor": ["低毛利提成折扣线", "percent"],
  "commission.low_margin_factor": ["低毛利时提成系数", "times"],
  "expense.entertainment_per_person": ["客户招待标准（每人）", "fen"],
  "expense.rule_ref": ["报销制度条款", "plain"],
  "attachment.max_bytes": ["单个票据大小上限", "bytes"],
  "agent.margin_max_retries": ["毛利不达标时最多重新配置次数", "plain"],
  "agent.max_tool_calls": ["单轮最多工具调用次数", "plain"],
  "pack.vram_headroom": ["显存余量系数", "times"],
  "pack.default_context_tokens": ["默认单请求上下文长度", "tokens"],
  "pack.tensor_parallel_sizes": ["可选张量并行规模（卡数）", "plain"],
  "pack.economy_discount_ladder": ["经济版折扣阶梯（逐级回退）", "percent"],
}

const TIER_NAMES: Record<string, string> = { economy: "经济版", standard: "标准版", premium: "旗舰版" }

const TIER_FIELDS: Record<string, string> = {
  gpu: "GPU",
  precision: "精度",
  ha: "高可用",
  tuning_days: "调优天数",
  maint_years: "维保年限",
  office: "办公机型",
  design: "设计机型",
  monitor_for_design: "设计岗配显示器",
  warranty: "延保",
}

function fmtScalar(v: unknown, fmt: Fmt): string {
  if (typeof v === "boolean") return v ? "是" : "否"
  if (typeof v !== "number") return String(v)
  switch (fmt) {
    case "percent":
      return `${Number((v * 100).toFixed(2))}%`
    case "fen":
      return formatFen(v)
    case "bytes":
      return v >= 1048576 ? `${Number((v / 1048576).toFixed(1))} MB` : `${Math.round(v / 1024)} KB`
    case "times":
      return `${v} 倍`
    case "days":
      return `${v} 天`
    case "years":
      return `${v} 年`
    case "tokens":
      return `${v.toLocaleString("zh-CN")} tokens`
    default:
      return String(v)
  }
}

export function formatRuleValue(v: unknown, fmt: Fmt = "plain"): string {
  if (Array.isArray(v)) return v.map((x) => fmtScalar(x, fmt)).join(" / ")
  if (v === null || v === undefined) return "—"
  if (typeof v === "object") return JSON.stringify(v)
  return fmtScalar(v, fmt)
}

export interface RuleRow {
  key: string
  label: string
  value: string
}

/** 方案档位：{gpu: L20, ha: false, ...} → 「GPU L20 · 高可用 否 · 调优天数 5」 */
function tierText(spec: unknown): string {
  if (typeof spec !== "object" || spec === null) return formatRuleValue(spec)
  return Object.entries(spec as Record<string, unknown>)
    .map(([k, v]) => `${TIER_FIELDS[k] ?? k} ${formatRuleValue(v)}`)
    .join(" · ")
}

const isPlainObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v)

/** 规则对象拍平成「中文说明 + 值」列表；未知的键保留原始路径，不丢信息 */
export function describeRules(rules: Record<string, unknown>, prefix = ""): RuleRow[] {
  const rows: RuleRow[] = []
  for (const [k, v] of Object.entries(rules)) {
    const key = prefix ? `${prefix}.${k}` : k
    if (key === "pack.tiers" && isPlainObject(v)) {
      for (const [tier, spec] of Object.entries(v))
        rows.push({ key: `${key}.${tier}`, label: `方案档位 · ${TIER_NAMES[tier] ?? tier}`, value: tierText(spec) })
      continue
    }
    const known = RULE_LABELS[key]
    if (isPlainObject(v) && !known) {
      rows.push(...describeRules(v, key))
      continue
    }
    rows.push({ key, label: known?.[0] ?? key, value: formatRuleValue(v, known?.[1]) })
  }
  return rows
}

/** 文件大小：字节 → KB / MB */
export function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return "—"
  if (n < 1024) return `${n} B`
  if (n < 1048576) return `${Number((n / 1024).toFixed(1))} KB`
  return `${Number((n / 1048576).toFixed(1))} MB`
}

/** 规格：对象 → 「key: value」逗号串；字符串原样 */
export function specText(specs: PackCatalogItem["specs"]): string {
  if (!specs) return ""
  if (typeof specs === "string") return specs
  return Object.entries(specs)
    .map(([k, v]) => `${k}: ${formatRuleValue(v)}`)
    .join("，")
}
