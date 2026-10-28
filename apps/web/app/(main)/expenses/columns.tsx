import { Building2, Calendar, CircleAlert, CircleDot, Coins, Hash, Paperclip, Tag as TagIcon, Text } from "lucide-react"

import { Chip } from "@/components/biz/Chip"
import type { GridColumn } from "@/components/biz/DataGrid"
import { Tag } from "@/components/biz/Tag"
import { formatFen } from "@/lib/format"
import { EXPENSE_STATUS_META, EXPENSE_TYPE_META, labelOf } from "@/lib/labels"
import { fenToYuan, type CsvColumn, type FilterDef, type SortAccessors } from "@/lib/list-view"
import type { ExpenseItem } from "@/types/api"

/** 报销网格列（与原型 ExpenseGrid 一致；发生日期、事由是次要列） */
export function expenseColumns(onOpen: (e: ExpenseItem) => void): GridColumn<ExpenseItem>[] {
  return [
    {
      id: "code",
      label: "单号",
      icon: Hash,
      width: "w-[120px]",
      cell: (e) => (
        <button type="button" onClick={() => onOpen(e)} className="font-medium hover:underline">
          {e.code}
        </button>
      ),
    },
    {
      id: "type",
      label: "类型",
      icon: TagIcon,
      cell: (e) => {
        const m = labelOf(EXPENSE_TYPE_META, e.type)
        return <Tag color={m.color}>{m.label}</Tag>
      },
    },
    { id: "amount", label: "金额", icon: Coins, align: "right", cell: (e) => formatFen(e.amount) },
    { id: "date", label: "发生日期", icon: Calendar, secondary: true, cell: (e) => e.occurred_on.slice(5, 10) },
    {
      id: "customer",
      label: "关联客户",
      icon: Building2,
      cell: (e) => (e.customer ? <Chip name={e.customer.name} logo={e.customer.name.slice(0, 1)} /> : "—"),
    },
    {
      id: "reason",
      label: "事由",
      icon: Text,
      secondary: true,
      cell: (e) => <span title={e.reason ?? undefined}>{e.reason || "—"}</span>,
    },
    {
      id: "attachments",
      label: "票据",
      icon: Paperclip,
      cell: (e) =>
        e.attachment_count > 0 ? (
          <span className="inline-flex h-5 items-center gap-1 rounded bg-zinc-100 px-1.5 text-zinc-600">
            <Paperclip className="size-3" />
            {e.attachment_count}
          </span>
        ) : e.status === "draft" ? (
          <span className="inline-flex items-center gap-1 text-red-600">
            <CircleAlert className="size-3.5" />
            缺票据
          </span>
        ) : (
          "—"
        ),
    },
    {
      id: "status",
      label: "状态",
      icon: CircleDot,
      status: true,
      cell: (e) => {
        const m = labelOf(EXPENSE_STATUS_META, e.status)
        const label = e.over_limit && e.status === "pending_approval" ? `超标 · ${m.label}` : m.label
        return <Tag color={m.color}>{label}</Tag>
      },
    },
  ]
}

/* ---------- ViewBar：筛选 / 排序 / 导出 ---------- */
export const expenseFilters: FilterDef<ExpenseItem>[] = [
  {
    id: "type",
    label: "类型",
    options: (Object.keys(EXPENSE_TYPE_META) as ExpenseItem["type"][]).map((t) => ({
      value: t,
      label: EXPENSE_TYPE_META[t].label,
    })),
    get: (e) => e.type,
  },
  {
    id: "status",
    label: "状态",
    options: (Object.keys(EXPENSE_STATUS_META) as ExpenseItem["status"][]).map((s) => ({
      value: s,
      label: EXPENSE_STATUS_META[s].label,
    })),
    get: (e) => e.status,
  },
  {
    id: "over",
    label: "是否超标",
    options: [
      { value: "yes", label: "超标" },
      { value: "no", label: "未超标" },
    ],
    get: (e) => (e.over_limit ? "yes" : "no"),
  },
]

export const expenseSort: SortAccessors<ExpenseItem> = { updated: (e) => e.created_at, amount: (e) => e.amount }

export const expenseCsv: CsvColumn<ExpenseItem>[] = [
  { label: "单号", value: (e) => e.code },
  { label: "类型", value: (e) => labelOf(EXPENSE_TYPE_META, e.type).label },
  { label: "金额（元）", value: (e) => fenToYuan(e.amount) },
  { label: "人数", value: (e) => e.headcount },
  { label: "发生日期", value: (e) => e.occurred_on },
  { label: "关联客户", value: (e) => e.customer?.name },
  { label: "事由", value: (e) => e.reason },
  { label: "票据数", value: (e) => e.attachment_count },
  { label: "是否超标", value: (e) => (e.over_limit ? "是" : "否") },
  { label: "状态", value: (e) => labelOf(EXPENSE_STATUS_META, e.status).label },
]
