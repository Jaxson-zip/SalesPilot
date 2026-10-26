import { Boxes, Building2, Calendar, CircleDot, Coins, Hash, Percent, Sparkles, User } from "lucide-react"
import Link from "next/link"

import { Chip } from "@/components/biz/Chip"
import type { GridColumn } from "@/components/biz/DataGrid"
import { Tag } from "@/components/biz/Tag"
import { formatFen, formatPercent, formatRelative } from "@/lib/format"
import { labelOf, QUOTE_STATUS_META } from "@/lib/labels"
import type { QuoteItem } from "@/types/api"
import { PackName } from "@/components/biz/PackName"

/** 报价单网格列（与原型 QuoteGrid 一致；方案 / 创建人 / 创建时间是次要列） */
export const quoteColumns: GridColumn<QuoteItem>[] = [
  {
    id: "code",
    label: "编号",
    icon: Hash,
    width: "w-[140px]",
    cell: (q) => (
      <Link href={`/quotes/${encodeURIComponent(q.id)}`} className="font-medium hover:underline">
        {q.code}
      </Link>
    ),
  },
  {
    id: "customer",
    label: "客户",
    icon: Building2,
    cell: (q) => (q.customer ? <Chip name={q.customer.name} logo={q.customer.name.slice(0, 1)} /> : "—"),
  },
  {
    id: "tier",
    label: "方案",
    icon: Boxes,
    secondary: true,
    cell: (q) => (
      <>
        <PackName id={q.pack} />
        {q.tier_name ? ` · ${q.tier_name}` : null}
      </>
    ),
  },
  { id: "amount", label: "金额", icon: Coins, align: "right", cell: (q) => formatFen(q.total_price) },
  {
    id: "margin",
    label: "毛利率",
    icon: Percent,
    align: "right",
    // 是否低于底线由 core 判断（status=pending_approval），前端不硬编码阈值
    cell: (q) => (
      <span className={q.status === "pending_approval" ? "text-red-600" : undefined}>
        {formatPercent(q.margin_rate)}
      </span>
    ),
  },
  {
    id: "status",
    label: "状态",
    icon: CircleDot,
    status: true,
    cell: (q) => {
      const m = labelOf(QUOTE_STATUS_META, q.status)
      return <Tag color={m.color}>{m.label}</Tag>
    },
  },
  {
    id: "owner",
    label: "创建人",
    icon: User,
    secondary: true,
    cell: (q) => (q.source === "agent" ? <Chip name="AI" icon={Sparkles} /> : <Chip name={q.owner.name} />),
  },
  { id: "created", label: "创建时间", icon: Calendar, secondary: true, cell: (q) => formatRelative(q.created_at) },
]
