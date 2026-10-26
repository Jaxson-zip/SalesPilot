import { Banknote, Building2, ChartNoAxesColumn, CircleDot, Coins, Hash, Wallet } from "lucide-react"
import Link from "next/link"

import { Chip } from "@/components/biz/Chip"
import type { GridColumn } from "@/components/biz/DataGrid"
import { ProgressBar } from "@/components/biz/Progress"
import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { paidPercent } from "@/lib/contract"
import { formatFen } from "@/lib/format"
import { CONTRACT_STATUS_META, labelOf } from "@/lib/labels"
import type { ContractItem } from "@/types/api"

/** 合同网格列（与原型 ContractGrid 一致）；canPay 时追加「登记回款」操作列 */
export function contractColumns(onPay?: (c: ContractItem) => void): GridColumn<ContractItem>[] {
  const cols: GridColumn<ContractItem>[] = [
    {
      id: "code",
      label: "合同编号",
      icon: Hash,
      width: "w-[130px]",
      cell: (c) => <span className="font-medium">{c.code}</span>,
    },
    {
      id: "customer",
      label: "客户",
      icon: Building2,
      cell: (c) => (c.customer ? <Chip name={c.customer.name} logo={c.customer.name.slice(0, 1)} /> : "—"),
    },
    { id: "amount", label: "合同金额", icon: Coins, align: "right", cell: (c) => formatFen(c.amount) },
    {
      id: "progress",
      label: "回款进度",
      icon: ChartNoAxesColumn,
      cell: (c) => <ProgressBar percent={paidPercent(c.paid_ratio)} />,
    },
    {
      id: "quote",
      label: "报价单",
      icon: Hash,
      secondary: true,
      cell: (c) =>
        c.quote ? (
          <Link href={`/quotes/${c.quote.id}`} className="hover:underline">
            {c.quote.code}
          </Link>
        ) : (
          "—"
        ),
    },
    {
      id: "estimated",
      label: "预估提成",
      icon: Wallet,
      align: "right",
      cell: (c) => formatFen(c.commission.estimated),
    },
    {
      id: "confirmed",
      label: "已确认提成",
      icon: Wallet,
      align: "right",
      secondary: true,
      cell: (c) => formatFen(c.commission.confirmed),
    },
    {
      id: "status",
      label: "状态",
      icon: CircleDot,
      status: true,
      cell: (c) => {
        const m = labelOf(CONTRACT_STATUS_META, c.status)
        return <Tag color={m.color}>{m.label}</Tag>
      },
    },
  ]
  if (onPay) {
    cols.push({
      id: "pay",
      label: "回款",
      icon: Banknote,
      cell: (c) =>
        c.status === "active" ? (
          <Button size="xs" variant="outline" onClick={() => onPay(c)}>
            登记回款
          </Button>
        ) : (
          <span className="text-zinc-400">—</span>
        ),
    })
  }
  return cols
}
