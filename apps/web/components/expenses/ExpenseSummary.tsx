import { Building2, Calendar, CircleDot, Coins, Tag as TagIcon, Text, Users } from "lucide-react"

import { Chip } from "@/components/biz/Chip"
import { FieldRow } from "@/components/biz/FieldRow"
import { Tag } from "@/components/biz/Tag"
import { formatFen } from "@/lib/format"
import { EXPENSE_STATUS_META, EXPENSE_TYPE_META, labelOf } from "@/lib/labels"
import type { ExpenseDetail } from "@/types/api"

/** 已保存报销单的字段（草稿没有修改接口，保存后字段只读） */
export function ExpenseSummary({ e }: { e: ExpenseDetail }) {
  const type = labelOf(EXPENSE_TYPE_META, e.type)
  const status = labelOf(EXPENSE_STATUS_META, e.status)
  return (
    <div className="-mx-1.5">
      <FieldRow icon={CircleDot} label="状态">
        <Tag color={status.color}>{status.label}</Tag>
      </FieldRow>
      <FieldRow icon={TagIcon} label="费用类型">
        <Tag color={type.color}>{type.label}</Tag>
      </FieldRow>
      <FieldRow icon={Coins} label="金额">
        <span className="tabular-nums">
          {formatFen(e.amount)} · {e.headcount} 人
        </span>
      </FieldRow>
      <FieldRow icon={Calendar} label="发生日期">
        {e.occurred_on}
      </FieldRow>
      <FieldRow icon={Building2} label="关联客户">
        {e.customer ? <Chip name={e.customer.name} logo={e.customer.name.slice(0, 1)} /> : "—"}
      </FieldRow>
      <FieldRow icon={Users} label="参与人">
        <span title={e.participants ?? undefined}>{e.participants || "—"}</span>
      </FieldRow>
      <FieldRow icon={Text} label="事由">
        <span title={e.reason}>{e.reason || "—"}</span>
      </FieldRow>
    </div>
  )
}
