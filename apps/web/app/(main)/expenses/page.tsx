"use client"

import { Plus, Receipt, X } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { BulkBar } from "@/components/biz/BulkBar"
import { DataGrid } from "@/components/biz/DataGrid"
import { EmptyState } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { RuleHint } from "@/components/biz/RuleHint"
import { QueryError } from "@/components/biz/QueryStatus"
import { ViewBar, type ViewOption } from "@/components/biz/ViewBar"
import { ExpenseSheet } from "@/components/expenses/ExpenseSheet"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { useExpenses } from "@/hooks/useExpenses"
import { useListView } from "@/hooks/useListView"
import { useOpportunity } from "@/hooks/useOpportunities"
import { usePermissions } from "@/hooks/usePermissions"
import { useRowSelection } from "@/hooks/useRowSelection"
import { EXPENSE_STATUS_META } from "@/lib/labels"
import { serverQuery } from "@/lib/list-view"
import { fetchAllPages, PAGE_SIZE } from "@/lib/paging"
import type { ExpenseItem, ExpenseStatus } from "@/types/api"

import { expenseColumns, expenseCsv, expenseFilters } from "./columns"

const STATUS_VIEWS: ExpenseStatus[] = ["draft", "pending_approval", "approved", "rejected", "paid"]
/** 第一个视图：销售 / 主管看自己的报销（团队报销在审批中心处理），管理员只读查看全部 */
function viewsFor(admin: boolean): ViewOption[] {
  return [
    { value: "all", label: admin ? "全部报销" : "我的报销" },
    ...STATUS_VIEWS.map((s) => ({ value: s, label: EXPENSE_STATUS_META[s].label })),
  ]
}

function toStatus(v: string): ExpenseStatus | undefined {
  return STATUS_VIEWS.find((s) => s === v)
}

const TOGGLEABLE = expenseColumns(() => undefined)
  .slice(1)
  .map((c) => ({ id: c.id, label: c.label }))

/** 报销：表格 + 新建报销 Sheet（报销始终是「我的」，团队报销在审批中心处理） */
const expenseId = (r: ExpenseItem) => r.id

export default function ExpensesPage() {
  const { role } = useSession()
  const { canCreate } = usePermissions()
  const admin = role === "admin"
  const [view, setView] = useState("all")
  const [sheet, setSheet] = useState<{ open: boolean; id: string | null }>({ open: false, id: null })
  // 从审批结果 / 动态通知跳转过来：/expenses?id=<报销 id> 直接打开这张报销单；
  // 从商机侧栏「跟单费用」过来：/expenses?opp=<商机 id> 只看这一单的费用（不用 useSearchParams，避免整页需要 Suspense）
  const [opp, setOpp] = useState<string | null>(null)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const id = params.get("id")
    if (id) setSheet({ open: true, id })
    setOpp(params.get("opp"))
  }, [])
  const oppName = useOpportunity(opp).data?.name
  const clearOpp = () => {
    setOpp(null)
    window.history.replaceState(null, "", "/expenses")
  }
  // 按商机看时用 all：本人的和（主管）本团队的都算这单的费用，范围仍由后端按权限过滤
  const scope = admin || opp ? "all" : "mine"
  const status = toStatus(view)
  const allColumns = useMemo(() => expenseColumns((e) => setSheet({ open: true, id: e.id })), [])
  const lv = useListView<ExpenseItem>({
    entity: "expenses",
    page: "expenses",
    rows: [],
    filters: expenseFilters,
    csv: expenseCsv,
    columns: TOGGLEABLE,
    exportName: "报销",
    server: {
      total: () => query.data?.total,
      fetchAll: (p) =>
        fetchAllPages<ExpenseItem>("/api/expenses", {
          view: scope,
          status,
          opportunity_id: opp ?? undefined,
          ...serverQuery(p),
        }),
    },
  })
  const query = useExpenses(
    { view: scope, status, opportunity_id: opp ?? undefined, page: lv.pageNo, page_size: PAGE_SIZE },
    lv.params,
  )
  const rows = useMemo(() => query.data?.items ?? [], [query.data])
  const columns = useMemo(() => allColumns.filter((c) => !lv.hidden.includes(c.id)), [allColumns, lv.hidden])
  const filtered = Object.keys(lv.bar.activeFilters).length > 0
  const sel = useRowSelection(rows, expenseId)
  const toPage = (n: number) => {
    sel.clear()
    lv.setPageNo(n)
  }
  const openNew = () => setSheet({ open: true, id: null })

  return (
    <PageFrame
      title="报销"
      icon={Receipt}
      actions={
        <>
          <RuleHint noteKey="expense" label="报销标准" />
          {canCreate ? <FrameAction icon={Plus} label="新建报销" primary onClick={openNew} /> : null}
        </>
      }
    >
      {sel.count ? (
        <BulkBar count={sel.count} onExport={() => lv.exportRows(sel.selected)} onClear={sel.clear} />
      ) : (
        <ViewBar
          views={viewsFor(admin)}
          value={view}
          onValueChange={(v) => {
            setView(v)
            toPage(1)
          }}
          count={query.data?.total}
          list={lv.bar}
        />
      )}
      {opp ? (
        <div role="status" className="flex items-center gap-2 border-b border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs">
          <span className="min-w-0 truncate text-zinc-600">只看商机「{oppName ?? "…"}」的跟单费用</span>
          <Button variant="ghost" size="xs" onClick={clearOpp}>
            <X />
            看全部报销
          </Button>
        </div>
      ) : null}
      {query.isError && !query.data ? (
        <QueryError
          error={query.error}
          onRetry={() => void query.refetch()}
          retrying={query.isFetching}
          feature="报销"
        />
      ) : (
        <DataGrid
          columns={columns}
          data={rows}
          getRowId={expenseId}
          selection={sel.selection}
          onSelectionChange={sel.setSelection}
          loading={query.isPending}
          total={query.data?.total}
          pagination={{ page: lv.pageNo, pageSize: PAGE_SIZE, onPageChange: toPage }}
          onAddRow={canCreate ? openNew : undefined}
          empty={
            filtered ? (
              <EmptyState icon={Receipt} title="没有符合筛选条件的报销单" description="可以在上方清除筛选。" />
            ) : (
              <EmptyState
                icon={Receipt}
                title="还没有报销单"
                description={canCreate ? "新建报销时会实时校验报销制度，超标的自动进入主管审批。" : undefined}
                action={
                  canCreate ? (
                    <Button size="sm" onClick={openNew}>
                      <Plus />
                      新建报销
                    </Button>
                  ) : undefined
                }
              />
            )
          }
        />
      )}
      <ExpenseSheet open={sheet.open} expenseId={sheet.id} onClose={() => setSheet({ open: false, id: null })} />
    </PageFrame>
  )
}
