import { Building2, Clock, Coins, Link as LinkIcon, Star, Tag as TagIcon, User } from "lucide-react"
import Link from "next/link"

import { Chip, LinkChip } from "@/components/biz/Chip"
import type { GridColumn } from "@/components/biz/DataGrid"
import { colorFor, Tag, type TagColor } from "@/components/biz/Tag"
import { displayHost, formatFen, formatRelative } from "@/lib/format"
import { fenToYuan, optionsFromRows, type CsvColumn, type FilterDef, type SortAccessors } from "@/lib/list-view"
import type { Customer } from "@/types/api"

function levelColor(level: string): TagColor {
  const head = level.trim().charAt(0).toUpperCase()
  if (head === "A") return "red"
  if (head === "B") return "blue"
  return "gray"
}

/** 客户网格列（与原型 CustomerGrid 一致；「网站」是次要列，<1024 隐藏） */
export const customerColumns: GridColumn<Customer>[] = [
  {
    id: "name",
    label: "客户名称",
    icon: Building2,
    width: "w-[220px]",
    cell: (c) => (
      <Link href={`/customers/${encodeURIComponent(c.id)}`} className="inline-flex max-w-full hover:underline">
        <Chip name={c.name} logo={c.name.slice(0, 1)} />
      </Link>
    ),
  },
  {
    id: "industry",
    label: "行业",
    icon: TagIcon,
    cell: (c) => (c.industry ? <Tag color={colorFor(c.industry)}>{c.industry}</Tag> : "—"),
  },
  {
    id: "level",
    label: "等级",
    icon: Star,
    cell: (c) => (c.level ? <Tag color={levelColor(c.level)}>{c.level}</Tag> : "—"),
  },
  { id: "owner", label: "负责人", icon: User, cell: (c) => <Chip name={c.owner.name} /> },
  {
    id: "website",
    label: "网站",
    icon: LinkIcon,
    secondary: true,
    cell: (c) => (c.website ? <LinkChip>{displayHost(c.website)}</LinkChip> : "—"),
  },
  { id: "amount", label: "商机金额", icon: Coins, align: "right", cell: (c) => formatFen(c.opportunity_amount) },
  { id: "followup", label: "最近跟进", icon: Clock, cell: (c) => formatRelative(c.last_followup_at) },
]

/* ---------- ViewBar：筛选 / 排序 / 导出（客户列表接口只有 q 参数，均在前端处理） ---------- */
export function customerFilters(rows: Customer[]): FilterDef<Customer>[] {
  return [
    {
      id: "level",
      label: "等级",
      options: ["A", "B", "C"].map((v) => ({ value: v, label: `${v} 级` })),
      get: (c) => c.level?.trim().charAt(0).toUpperCase() || null,
    },
    {
      id: "industry",
      label: "行业",
      options: optionsFromRows(rows, (c) => c.industry),
      get: (c) => c.industry || null,
    },
    {
      id: "owner",
      label: "负责人",
      options: optionsFromRows(rows, (c) => c.owner.name),
      get: (c) => c.owner.name,
    },
  ]
}

export const customerSort: SortAccessors<Customer> = {
  updated: (c) => c.last_followup_at,
  amount: (c) => c.opportunity_amount,
}

export const customerCsv: CsvColumn<Customer>[] = [
  { label: "客户名称", value: (c) => c.name },
  { label: "行业", value: (c) => c.industry },
  { label: "等级", value: (c) => c.level },
  { label: "负责人", value: (c) => c.owner.name },
  { label: "网站", value: (c) => c.website },
  { label: "商机金额（元）", value: (c) => fenToYuan(c.opportunity_amount) },
  { label: "最近跟进", value: (c) => c.last_followup_at },
]
