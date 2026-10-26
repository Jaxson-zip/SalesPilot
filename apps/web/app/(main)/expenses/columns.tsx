import { Building2, Calendar, CircleAlert, CircleDot, Coins, Hash, Paperclip, Tag as TagIcon, Text } from "lucide-react"

import { Chip } from "@/components/biz/Chip"
import type { GridColumn } from "@/components/biz/DataGrid"
import { Tag } from "@/components/biz/Tag"
import { formatFen } from "@/lib/format"
import { EXPENSE_STATUS_META, EXPENSE_TYPE_META, labelOf } from "@/lib/labels"
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
    { id: "reason", label: "事由", icon: Text, secondary: true, cell: (e) => <span title={e.reason}>{e.reason}</span> },
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
