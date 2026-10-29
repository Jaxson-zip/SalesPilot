import { Banknote, Building2, CalendarClock, ChartNoAxesColumn, CircleDot, Coins, Hash, Wallet } from "lucide-react"
import Link from "next/link"

import { Chip } from "@/components/biz/Chip"
import type { GridColumn } from "@/components/biz/DataGrid"
import { ProgressBar } from "@/components/biz/Progress"
import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { paidPercent } from "@/lib/contract"
import { formatFen, ownerName } from "@/lib/format"
import { CONTRACT_STATUS_META, labelOf } from "@/lib/labels"
import { fenToYuan, type CsvColumn, type FilterDef, type FilterOption } from "@/lib/list-view"
import type { ContractItem } from "@/types/api"

/** 下期回款（B9）：期次 + 还差金额 + 到期日；逾期标红 */
function NextPaymentCell({ c }: { c: ContractItem }) {
  const n = c.next_payment
  if (!n) return <span className="text-zinc-400">已收齐</span>
  return (
    <span className="inline-flex items-center gap-1.5">
      <span>
        {n.name} {formatFen(n.amount)}
      </span>
      {n.status === "overdue" ? (
        <Tag color="red">逾期 {n.overdue_days} 天</Tag>
      ) : (
        <span className="text-xs text-zinc-500">{n.due_date.slice(5)} 到期</span>
      )}
    </span>
  )
}

/** 合同网格列（与原型 ContractGrid 一致）；canPay 时追加「登记回款」操作列；点合同编号看回款计划 */
export function contractColumns(
  onPay?: (c: ContractItem) => void,
  onOpenPlan?: (c: ContractItem) => void,
): GridColumn<ContractItem>[] {
  const cols: GridColumn<ContractItem>[] = [
    {
      id: "code",
      label: "合同编号",
      icon: Hash,
      width: "w-[170px]",
      cell: (c) =>
        onOpenPlan ? (
          <span className="inline-flex min-w-0 items-center gap-1.5">
            <button type="button" className="font-medium hover:underline" onClick={() => onOpenPlan(c)}>
              {c.code}
            </button>
            {/* 有期次申请了开票、等主管登记 */}
            {c.invoice_requested ? (
              <button type="button" onClick={() => onOpenPlan(c)} title="有开票申请待处理">
                <Tag color="orange">待开票</Tag>
              </button>
            ) : null}
          </span>
        ) : (
          <span className="font-medium">{c.code}</span>
        ),
    },
    {
      id: "customer",
      label: "客户",
      icon: Building2,
      // 列多：客户按比例给宽度（避免公司名被截成三个字），其余列平分
      width: "w-[14%]",
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
      id: "next_payment",
      label: "下期回款",
      icon: CalendarClock,
      width: "w-[230px]",
      cell: (c) => <NextPaymentCell c={c} />,
    },
    {
      id: "quote",
      label: "报价单",
      icon: Hash,
      secondary: "wide",
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
      secondary: "wide",
      cell: (c) => formatFen(c.commission.confirmed),
    },
    {
      id: "status",
      label: "状态",
      icon: CircleDot,
      status: true,
      width: "w-[84px]",
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

/* ---------- ViewBar：筛选 / 排序 / 导出 ---------- */
/** 服务端筛选：客户、负责人的选项来自 /api/contracts/facets（整个范围） */
export function contractFilters(facets: Record<string, FilterOption[]> | undefined): FilterDef<ContractItem>[] {
  return [
    {
      id: "status",
      label: "状态",
      param: "status_in",
      options: (Object.keys(CONTRACT_STATUS_META) as ContractItem["status"][]).map((s) => ({
        value: s,
        label: CONTRACT_STATUS_META[s].label,
      })),
    },
    {
      id: "overdue",
      label: "回款",
      options: [
        { value: "overdue", label: "有逾期" },
        { value: "ok", label: "无逾期" },
      ],
    },
    { id: "customer", label: "客户", param: "customer_in", options: facets?.customer ?? [] },
    { id: "owner", label: "负责人", param: "owner_in", options: facets?.owner ?? [] },
  ]
}

export const contractCsv: CsvColumn<ContractItem>[] = [
  { label: "合同编号", value: (c) => c.code },
  { label: "客户", value: (c) => c.customer?.name },
  { label: "报价单", value: (c) => c.quote?.code },
  { label: "合同金额（元）", value: (c) => fenToYuan(c.amount) },
  { label: "已回款（元）", value: (c) => fenToYuan(c.paid_amount) },
  { label: "回款比例", value: (c) => `${paidPercent(c.paid_ratio)}%` },
  {
    label: "下期回款",
    value: (c) => (c.next_payment ? `${c.next_payment.name} ${c.next_payment.due_date}` : "已收齐"),
  },
  { label: "逾期未收（元）", value: (c) => fenToYuan(c.overdue_amount) },
  { label: "预估提成（元）", value: (c) => fenToYuan(c.commission.estimated) },
  { label: "已确认提成（元）", value: (c) => fenToYuan(c.commission.confirmed) },
  { label: "状态", value: (c) => labelOf(CONTRACT_STATUS_META, c.status).label },
  { label: "负责人", value: (c) => ownerName(c.owner) },
]
