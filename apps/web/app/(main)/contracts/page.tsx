"use client"

import { FileSignature } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { BulkBar } from "@/components/biz/BulkBar"
import { DataGrid } from "@/components/biz/DataGrid"
import { EmptyState } from "@/components/biz/EmptyState"
import { PageFrame } from "@/components/biz/PageFrame"
import { RuleHint } from "@/components/biz/RuleHint"
import { QueryError } from "@/components/biz/QueryStatus"
import { ViewBar, type ViewOption } from "@/components/biz/ViewBar"
import { PaymentDialog } from "@/components/contracts/PaymentDialog"
import { PaymentPlanSheet } from "@/components/contracts/PaymentPlanSheet"
import { useSession } from "@/components/shell/SessionProvider"
import { Skeleton } from "@/components/ui/skeleton"
import { useContract, useContracts } from "@/hooks/useContracts"
import { useFacets } from "@/hooks/useFacets"
import { useListView } from "@/hooks/useListView"
import { usePermissions } from "@/hooks/usePermissions"
import { useRowSelection } from "@/hooks/useRowSelection"
import { formatFen } from "@/lib/format"
import { CONTRACT_STATUS_META } from "@/lib/labels"
import { serverQuery } from "@/lib/list-view"
import { contractsLabel } from "@/lib/nav"
import { fetchAllPages, PAGE_SIZE } from "@/lib/paging"
import { defaultScope, scopeLabel } from "@/lib/views"
import { cn } from "@/lib/utils"
import type { ContractItem, ContractStatus, ContractSummary } from "@/types/api"

import { contractColumns, contractCsv, contractFilters } from "./columns"

const STATUS_OPTIONS: ViewOption[] = [
  { value: "active", label: CONTRACT_STATUS_META.active.label },
  { value: "paid", label: CONTRACT_STATUS_META.paid.label },
]

function toStatus(v: string): ContractStatus | undefined {
  return v === "active" || v === "paid" ? v : undefined
}

const TOGGLEABLE = contractColumns()
  .slice(1)
  .map((c) => ({ id: c.id, label: c.label }))

/**
 * StatStrip：本月成交 / 全部合同的预估提成 / 全部合同的待回款。
 * 每格写明时间范围：只有第一格按本月，后两格是全部合同（本月提成在工作台）；都不受页签和筛选影响。
 */
function StatStrip({ s, loading }: { s: ContractSummary | undefined; loading: boolean }) {
  const items = [
    { k: "本月成交", v: formatFen(s?.month_amount), sub: "本月新签合同金额" },
    {
      k: "预估提成 · 全部合同",
      v: formatFen(s?.estimated_commission),
      sub: s ? `已确认 ${formatFen(s.confirmed_commission)}` : "",
    },
    { k: "待回款 · 全部合同", v: formatFen(s?.unpaid_amount), sub: "不受筛选影响", wideOnly: true },
  ]
  return (
    // 手机上也是一行三格（原来竖排三块占掉半屏）
    <div className="grid shrink-0 grid-cols-3 divide-x divide-zinc-200 border-b border-zinc-200">
      {items.map((it) => (
        <div key={it.k} className="min-w-0 px-3 py-3 sm:px-5 sm:py-4">
          <div className="truncate text-zinc-500 max-sm:text-xs">{it.k}</div>
          {loading ? (
            <Skeleton className="mt-2 h-6 w-28" />
          ) : (
            <div className="mt-1 truncate text-base font-semibold tabular-nums sm:text-xl">{it.v}</div>
          )}
          <div className={cn("h-4 truncate text-xs text-zinc-500", "wideOnly" in it && "max-sm:invisible")}>
            {it.sub}
          </div>
        </div>
      ))}
    </div>
  )
}

const contractId = (r: ContractItem) => r.id

export default function ContractsPage() {
  const { role } = useSession()
  const views: ViewOption[] = [{ value: "all", label: scopeLabel(role, "合同") }, ...STATUS_OPTIONS]
  const { canPay, canEdit } = usePermissions()
  const payable = canPay()
  const [view, setView] = useState("all")
  const [paying, setPaying] = useState<ContractItem | null>(null)
  const [planOf, setPlanOf] = useState<ContractItem | null>(null)
  const scope = defaultScope(role)
  const status = toStatus(view)
  // 登记回款只给主管（契约 §0）；列内再按合同状态判断
  const withOwner = role !== "sales"
  const allColumns = useMemo(
    () => contractColumns(payable ? setPaying : undefined, setPlanOf, withOwner),
    [payable, withOwner],
  )
  // 从开票通知跳转过来：/contracts?plan=<合同 id> 直接打开回款计划（不用 useSearchParams，避免整页需要 Suspense）
  const [linked, setLinked] = useState<string | null>(null)
  useEffect(() => {
    setLinked(new URLSearchParams(window.location.search).get("plan"))
  }, [])
  const linkedContract = useContract(linked)
  useEffect(() => {
    if (linkedContract.data) {
      setPlanOf(linkedContract.data)
      setLinked(null)
    }
  }, [linkedContract.data])
  const facets = useFacets("contracts", { view: scope })
  const filters = useMemo(() => contractFilters(facets.data), [facets.data])
  const lv = useListView<ContractItem>({
    entity: "contracts",
    page: "contracts",
    rows: [],
    filters,
    csv: contractCsv,
    columns: withOwner ? TOGGLEABLE : TOGGLEABLE.filter((c) => c.id !== "owner"),
    exportName: "合同",
    server: {
      total: () => query.data?.total,
      fetchAll: (p) => fetchAllPages<ContractItem>("/api/contracts", { view: scope, status, ...serverQuery(p) }),
    },
  })
  const query = useContracts({ view: scope, status, page: lv.pageNo, page_size: PAGE_SIZE }, lv.params)
  const rows = useMemo(() => query.data?.items ?? [], [query.data])
  const columns = useMemo(() => allColumns.filter((c) => !lv.hidden.includes(c.id)), [allColumns, lv.hidden])
  const filtered = Object.keys(lv.bar.activeFilters).length > 0
  const sel = useRowSelection(rows, contractId)
  const toPage = (n: number) => {
    sel.clear()
    lv.setPageNo(n)
  }

  return (
    <PageFrame
      title={contractsLabel(role)}
      icon={FileSignature}
      actions={<RuleHint noteKey="commission" label="提成规则" />}
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
              views={views}
              value={view}
              onValueChange={(v) => {
                setView(v)
                toPage(1)
              }}
              count={query.data?.total}
              list={lv.bar}
            />
          )}
          <DataGrid
            columns={columns}
            data={rows}
            getRowId={contractId}
            selection={sel.selection}
            onSelectionChange={sel.setSelection}
            loading={query.isPending}
            total={query.data?.total}
            pagination={{ page: lv.pageNo, pageSize: PAGE_SIZE, onPageChange: toPage }}
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
      <PaymentPlanSheet
        contract={planOf}
        editable={canEdit(planOf?.owner?.id)}
        manager={role === "manager"}
        onClose={() => setPlanOf(null)}
      />
    </PageFrame>
  )
}
