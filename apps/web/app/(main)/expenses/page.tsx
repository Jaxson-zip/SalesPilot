"use client"

import { Plus, Receipt } from "lucide-react"
import { useMemo, useState } from "react"

import { BulkBar } from "@/components/biz/BulkBar"
import { DataGrid } from "@/components/biz/DataGrid"
import { EmptyState } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { ViewBar, type ViewOption } from "@/components/biz/ViewBar"
import { ExpenseSheet } from "@/components/expenses/ExpenseSheet"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { useExpenses } from "@/hooks/useExpenses"
import { useListView } from "@/hooks/useListView"
import { usePermissions } from "@/hooks/usePermissions"
import { useRowSelection } from "@/hooks/useRowSelection"
import { EXPENSE_STATUS_META } from "@/lib/labels"
import type { ExpenseItem, ExpenseStatus } from "@/types/api"

import { expenseColumns, expenseCsv, expenseFilters, expenseSort } from "./columns"

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
  const query = useExpenses({ view: admin ? "all" : "mine", status: toStatus(view), page: 1, page_size: 100 })
  const allColumns = useMemo(() => expenseColumns((e) => setSheet({ open: true, id: e.id })), [])
  const all = useMemo(() => query.data?.items ?? [], [query.data])
  const lv = useListView({
    page: "expenses",
    rows: all,
    filters: expenseFilters,
    sort: expenseSort,
    csv: expenseCsv,
    columns: TOGGLEABLE,
    exportName: "报销",
  })
  const columns = useMemo(() => allColumns.filter((c) => !lv.hidden.includes(c.id)), [allColumns, lv.hidden])
  const filtered = Object.keys(lv.bar.activeFilters).length > 0
  const sel = useRowSelection(lv.rows, expenseId)
  const openNew = () => setSheet({ open: true, id: null })

  return (
    <PageFrame
      title="报销"
      icon={Receipt}
      actions={canCreate ? <FrameAction icon={Plus} label="新建报销" primary onClick={openNew} /> : null}
    >
      {sel.count ? (
        <BulkBar count={sel.count} onExport={() => lv.exportRows(sel.selected)} onClear={sel.clear} />
      ) : (
        <ViewBar
          views={viewsFor(admin)}
          value={view}
          onValueChange={setView}
          count={filtered ? lv.rows.length : query.data?.total}
          list={lv.bar}
        />
      )}
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
          data={lv.rows}
          getRowId={expenseId}
          selection={sel.selection}
          onSelectionChange={sel.setSelection}
          loading={query.isPending}
          total={filtered ? lv.rows.length : query.data?.total}
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
