"use client"

import { Building2, Plus } from "lucide-react"
import { useMemo, useState } from "react"

import { DataGrid } from "@/components/biz/DataGrid"
import { EmptyState, ErrorState } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { ViewBar, type ViewOption } from "@/components/biz/ViewBar"
import { NewCustomerSheet } from "@/components/customers/NewCustomerSheet"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { useCustomers } from "@/hooks/useCustomers"
import { useListView } from "@/hooks/useListView"
import { usePermissions } from "@/hooks/usePermissions"
import type { CustomerView } from "@/types/api"

import { customerColumns, customerCsv, customerFilters, customerSort } from "./columns"

function isView(v: string): v is CustomerView {
  return v === "mine" || v === "team" || v === "all"
}

const TOGGLEABLE = customerColumns.slice(1).map((c) => ({ id: c.id, label: c.label }))

/** 客户列表：ViewBar（视图 / 筛选 / 排序 / 选项）+ DataGrid + 新建客户 Sheet */
export default function CustomersPage() {
  const { role } = useSession()
  const { canCreate } = usePermissions()
  const [selected, setView] = useState<CustomerView>("mine")
  const [creating, setCreating] = useState(false)
  const views: ViewOption[] =
    role === "admin"
      ? [{ value: "all", label: "全部客户" }]
      : role === "manager"
        ? [
            { value: "mine", label: "我负责的" },
            { value: "team", label: "团队客户" },
          ]
        : [{ value: "mine", label: "我的客户" }]
  // 切换角色后原视图可能不可用（例如主管 → 销售），回落到第一个视图
  const first = views[0].value
  const view: CustomerView = views.some((v) => v.value === selected) ? selected : isView(first) ? first : "mine"

  // 筛选 / 排序在前端处理，一次取满一页（接口上限 100）
  const query = useCustomers({ view, page: 1, page_size: 100 })
  const all = useMemo(() => query.data?.items ?? [], [query.data])
  const filters = useMemo(() => customerFilters(all), [all])
  const lv = useListView({
    page: "customers",
    rows: all,
    filters,
    sort: customerSort,
    csv: customerCsv,
    columns: TOGGLEABLE,
    exportName: "客户",
  })
  const columns = useMemo(() => customerColumns.filter((c) => !lv.hidden.includes(c.id)), [lv.hidden])
  const filtered = Object.keys(lv.bar.activeFilters).length > 0
  const openNew = canCreate ? () => setCreating(true) : undefined

  return (
    <PageFrame
      title="客户"
      icon={Building2}
      actions={
        canCreate ? <FrameAction icon={Plus} label="新建客户" primary onClick={() => setCreating(true)} /> : null
      }
    >
      <ViewBar
        views={views}
        value={view}
        onValueChange={(v) => isView(v) && setView(v)}
        count={filtered ? lv.rows.length : query.data?.total}
        list={lv.bar}
      />
      {query.isError && !query.data ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} />
      ) : (
        <DataGrid
          columns={columns}
          data={lv.rows}
          getRowId={(c) => c.id}
          loading={query.isPending}
          total={filtered ? lv.rows.length : query.data?.total}
          onAddRow={openNew}
          empty={
            filtered ? (
              <EmptyState icon={Building2} title="没有符合筛选条件的客户" description="可以在上方清除筛选。" />
            ) : (
              <EmptyState
                icon={Building2}
                title="还没有客户"
                description={canCreate ? "可以新建客户，或在 AI 方案工作台里让 AI 帮你录入。" : undefined}
                action={
                  canCreate ? (
                    <Button size="sm" onClick={() => setCreating(true)}>
                      <Plus />
                      新建客户
                    </Button>
                  ) : undefined
                }
              />
            )
          }
        />
      )}
      <NewCustomerSheet open={creating} onOpenChange={setCreating} />
    </PageFrame>
  )
}
