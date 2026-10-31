import { formatFen, formatPercent } from "@/lib/format"

/**
 * 确认卡片（interrupt.preview）的字段展示规则。
 * core 传的是原始业务字段（金额为分、比例为 0–1、带各种 id），这里转成给销售看的中文行。
 */
type Formatter = (v: unknown) => string

const fen: Formatter = (v) => (typeof v === "number" ? formatFen(v) : String(v))
const percent: Formatter = (v) => (typeof v === "number" ? formatPercent(v) : String(v))

const FIELDS: Record<string, { label: string; format?: Formatter }> = {
  customer_name: { label: "客户" },
  opportunity_name: { label: "商机" },
  name: { label: "方案" },
  summary: { label: "配置" },
  total_price: { label: "报价", format: fen },
  total_cost: { label: "成本", format: fen },
  margin_rate: { label: "毛利", format: percent },
  amount: { label: "金额", format: fen },
  headcount: { label: "人数" },
  expense_type: { label: "类型" },
  stage: { label: "阶段" },
  approver_name: { label: "审批人" },
  reason: { label: "事由" },
  // function calling 写操作（core app/agent/tools/previews.py）
  occurred_on: { label: "日期" },
  contacts: { label: "客户方" },
  colleagues: { label: "我方" },
  lost_reason: { label: "输单原因" },
  trip: { label: "行程" },
  target: { label: "单据" },
  task_title: { label: "任务" },
  due_at: { label: "到期" },
  task_type: { label: "方式" },
  decision: { label: "结果" },
  // 一手材料消化（digest_material）
  followup: { label: "跟进" },
  followup_type: { label: "方式" },
  new_contacts: { label: "联系人" },
  next_steps: { label: "下一步" },
  comment: { label: "意见" },
}

/** 内部字段不展示：各种 id、行业包 id、档位代号 */
const HIDDEN = new Set(["pack_id", "tier", "idempotency_key"])
const isHidden = (key: string): boolean => HIDDEN.has(key) || key === "id" || key.endsWith("_id")

export function previewRows(preview: Record<string, unknown>): [string, string][] {
  return Object.entries(preview)
    .filter(([k, v]) => !isHidden(k) && v !== null && v !== undefined && typeof v !== "object")
    .map(([k, v]) => {
      const field = FIELDS[k]
      if (!field) return [k, String(v)]
      return [field.label, field.format ? field.format(v) : String(v)]
    })
}
