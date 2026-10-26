"use client"

import { CircleDot, Coins, Plus, Receipt, Tag as TagIcon } from "lucide-react"
import { useMemo, useState } from "react"

import { DataGrid } from "@/components/biz/DataGrid"
import { EmptyState } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { ViewBar, type ViewOption } from "@/components/biz/ViewBar"
import { ExpenseSheet } from "@/components/expenses/ExpenseSheet"
import { Button } from "@/components/ui/button"
import { useExpenses } from "@/hooks/useExpenses"
import { EXPENSE_STATUS_META } from "@/lib/labels"
import type { ExpenseStatus } from "@/types/api"

import { expenseColumns } from "./columns"

const FILTER_FIELDS = [
  { label: "类型", icon: TagIcon },
  { label: "状态", icon: CircleDot },
  { label: "金额", icon: Coins },
]
const STATUS_VIEWS: ExpenseStatus[] = ["draft", "pending_approval", "approved", "rejected", "paid"]
const VIEWS: ViewOption[] = [
  { value: "all", label: "我的报销" },
  ...STATUS_VIEWS.map((s) => ({ value: s, label: EXPENSE_STATUS_META[s].label })),
]

function toStatus(v: string): ExpenseStatus | undefined {
  return STATUS_VIEWS.find((s) => s === v)
}

/** 报销：表格 + 新建报销 Sheet（报销始终是「我的」，团队报销在审批中心处理） */
export default function ExpensesPage() {
  const [view, setView] = useState("all")
  const [sheet, setSheet] = useState<{ open: boolean; id: string | null }>({ open: false, id: null })
  const query = useExpenses({ view: "mine", status: toStatus(view), page: 1, page_size: 50 })
  const columns = useMemo(() => expenseColumns((e) => setSheet({ open: true, id: e.id })), [])
  const openNew = () => setSheet({ open: true, id: null })

  return (
    <PageFrame
      title="报销"
      icon={Receipt}
      actions={<FrameAction icon={Plus} label="新建报销" primary onClick={openNew} />}
    >
      <ViewBar views={VIEWS} value={view} onValueChange={setView} count={query.data?.total} fields={FILTER_FIELDS} />
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
          data={query.data?.items ?? []}
          getRowId={(e) => e.id}
          loading={query.isPending}
          total={query.data?.total}
          onAddRow={openNew}
          empty={
            <EmptyState
              icon={Receipt}
              title="还没有报销单"
              description="新建报销时会实时校验报销制度，超标的自动进入主管审批。"
              action={
                <Button size="sm" onClick={openNew}>
                  <Plus />
                  新建报销
                </Button>
              }
            />
          }
        />
      )}
      <ExpenseSheet open={sheet.open} expenseId={sheet.id} onClose={() => setSheet({ open: false, id: null })} />
    </PageFrame>
  )
}
