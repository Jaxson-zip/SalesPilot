"use client"

import { FileSignature, Info } from "lucide-react"
import { useMemo, useState } from "react"

import { BulkBar } from "@/components/biz/BulkBar"
import { DataGrid } from "@/components/biz/DataGrid"
import { EmptyState } from "@/components/biz/EmptyState"
import { FormSheet } from "@/components/biz/FormSheet"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { ViewBar, type ViewOption } from "@/components/biz/ViewBar"
import { PaymentDialog } from "@/components/contracts/PaymentDialog"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useContracts } from "@/hooks/useContracts"
import { useListView } from "@/hooks/useListView"
import { usePermissions } from "@/hooks/usePermissions"
import { useRowSelection } from "@/hooks/useRowSelection"
import { formatFen } from "@/lib/format"
import { CONTRACT_STATUS_META } from "@/lib/labels"
import { contractsLabel } from "@/lib/nav"
import { defaultScope } from "@/lib/views"
import type { ContractItem, ContractStatus, ContractSummary } from "@/types/api"

import { contractColumns, contractCsv, contractFilters, contractSort } from "./columns"

const VIEWS: ViewOption[] = [
  { value: "all", label: "所有合同" },
  { value: "active", label: CONTRACT_STATUS_META.active.label },
  { value: "paid", label: CONTRACT_STATUS_META.paid.label },
]

function toStatus(v: string): ContractStatus | undefined {
  return v === "active" || v === "paid" ? v : undefined
}

const TOGGLEABLE = contractColumns()
  .slice(1)
  .map((c) => ({ id: c.id, label: c.label }))

/** StatStrip：本月成交 / 本月预估提成 / 待回款 */
function StatStrip({ s, loading }: { s: ContractSummary | undefined; loading: boolean }) {
  const items = [
    { k: "本月成交", v: formatFen(s?.month_amount) },
    {
      k: "本月预估提成",
      v: formatFen(s?.estimated_commission),
      sub: s ? `已确认 ${formatFen(s.confirmed_commission)}` : "",
    },
    { k: "待回款", v: formatFen(s?.unpaid_amount) },
  ]
  return (
    <div className="grid shrink-0 grid-cols-1 divide-y divide-zinc-200 border-b border-zinc-200 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
      {items.map((it) => (
        <div key={it.k} className="min-w-0 px-5 py-4">
          <div className="text-zinc-500">{it.k}</div>
          {loading ? (
            <Skeleton className="mt-2 h-6 w-28" />
          ) : (
            <div className="mt-1 truncate text-xl font-semibold tabular-nums">{it.v}</div>
          )}
          <div className="h-4 truncate text-xs text-zinc-500">{it.sub}</div>
        </div>
      ))}
    </div>
  )
}

/** 提成规则说明（具体比例与阈值在 rules.yaml，前端不写死数字） */
function RuleSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  return (
    <FormSheet
      open={open}
      onOpenChange={onOpenChange}
      title="提成规则"
      footer={<Button onClick={() => onOpenChange(false)}>知道了</Button>}
    >
      <div className="space-y-2 leading-6 text-zinc-700">
        <p>· 按物料类别（硬件 / 软件 / 服务）分别计提，比例见业务规则配置</p>
        <p>· 毛利率低于底线的合同，提成按规则打折</p>
        <p>· 合同成交时生成「预估提成」，按实际回款比例确认</p>
        <p className="pt-2 text-xs text-zinc-400">配置来源：rules.yaml（通用规则 + 行业包覆盖），由报价引擎计算</p>
      </div>
    </FormSheet>
  )
}

const contractId = (r: ContractItem) => r.id

export default function ContractsPage() {
  const { role } = useSession()
  const { canPay } = usePermissions()
  const payable = canPay()
  const [view, setView] = useState("all")
  const [paying, setPaying] = useState<ContractItem | null>(null)
  const [ruleOpen, setRuleOpen] = useState(false)
  const query = useContracts({ view: defaultScope(role), status: toStatus(view), page: 1, page_size: 100 })
  // 登记回款只给主管（契约 §0）；列内再按合同状态判断
  const allColumns = useMemo(() => contractColumns(payable ? setPaying : undefined), [payable])
  const all = useMemo(() => query.data?.items ?? [], [query.data])
  const filters = useMemo(() => contractFilters(all), [all])
  const lv = useListView({
    page: "contracts",
    rows: all,
    filters,
    sort: contractSort,
    csv: contractCsv,
    columns: TOGGLEABLE,
    exportName: "合同",
  })
  const columns = useMemo(() => allColumns.filter((c) => !lv.hidden.includes(c.id)), [allColumns, lv.hidden])
  const filtered = Object.keys(lv.bar.activeFilters).length > 0
  const sel = useRowSelection(lv.rows, contractId)

  return (
    <PageFrame
      title={contractsLabel(role)}
      icon={FileSignature}
      actions={<FrameAction icon={Info} label="提成规则" onClick={() => setRuleOpen(true)} />}
    >
      {query.isError && !query.data ? (
        <QueryError
          error={query.error}
          onRetry={() => void query.refetch()}
          retrying={query.isFetching}
          feature="合同"
        />
      ) : (
        <>
          <StatStrip s={query.data?.summary} loading={query.isPending} />
          {sel.count ? (
            <BulkBar count={sel.count} onExport={() => lv.exportRows(sel.selected)} onClear={sel.clear} />
          ) : (
            <ViewBar
              views={VIEWS}
              value={view}
              onValueChange={setView}
              count={filtered ? lv.rows.length : query.data?.total}
              list={lv.bar}
            />
          )}
          <DataGrid
            columns={columns}
            data={lv.rows}
            getRowId={contractId}
            selection={sel.selection}
            onSelectionChange={sel.setSelection}
            loading={query.isPending}
            total={filtered ? lv.rows.length : query.data?.total}
            empty={
              <EmptyState
                icon={FileSignature}
                title={filtered ? "没有符合筛选条件的合同" : "还没有合同"}
                description={filtered ? "可以在上方清除筛选。" : "报价单被客户接受后会自动生成合同和预估提成。"}
              />
            }
          />
        </>
      )}
      <PaymentDialog contract={paying} onClose={() => setPaying(null)} />
      <RuleSheet open={ruleOpen} onOpenChange={setRuleOpen} />
    </PageFrame>
  )
}
