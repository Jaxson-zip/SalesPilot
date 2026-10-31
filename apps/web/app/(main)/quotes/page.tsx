"use client"

import { FileText, Plus, Sparkles } from "lucide-react"
import Link from "next/link"
import { useMemo, useState } from "react"

import { BulkBar } from "@/components/biz/BulkBar"
import { DataGrid } from "@/components/biz/DataGrid"
import { EmptyState } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { ViewBar, type ViewOption } from "@/components/biz/ViewBar"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { PageTip } from "@/components/onboarding/PageTip"
import { useFacets } from "@/hooks/useFacets"
import { useListView } from "@/hooks/useListView"
import { usePermissions } from "@/hooks/usePermissions"
import { useRowSelection } from "@/hooks/useRowSelection"
import { usePacks } from "@/hooks/useProductLines"
import { useQuotes } from "@/hooks/useQuotes"
import { QUOTE_STATUS_META } from "@/lib/labels"
import { serverQuery } from "@/lib/list-view"
import { fetchAllPages, PAGE_SIZE } from "@/lib/paging"
import { defaultScope, scopeLabel } from "@/lib/views"
import { PAGE_TIPS } from "@/lib/onboarding"
import type { QuoteItem, QuoteStatus } from "@/types/api"

import { quoteColumns, quoteCsv, quoteFilters } from "./columns"

const STATUS_VIEWS: QuoteStatus[] = ["draft", "pending_approval", "approved", "sent", "accepted", "rejected"]
const STATUS_OPTIONS: ViewOption[] = STATUS_VIEWS.map((s) => ({ value: s, label: QUOTE_STATUS_META[s].label }))

function toStatus(v: string): QuoteStatus | undefined {
  return STATUS_VIEWS.find((s) => s === v)
}

const TOGGLEABLE = quoteColumns.slice(1).map((c) => ({ id: c.id, label: c.label }))

/** 报价单列表：按状态切换视图；数据范围跟随角色（销售本人 / 主管团队 / 管理员全部） */
const quoteId = (r: QuoteItem) => r.id

export default function QuotesPage() {
  const { role } = useSession()
  const { canAiWrite, canCreate } = usePermissions()
  const VIEWS: ViewOption[] = [{ value: "all", label: scopeLabel(role, "报价单") }, ...STATUS_OPTIONS]
  const [view, setView] = useState("all")
  // 页签里的状态、筛选、排序、分页都走接口参数
  const scope = defaultScope(role)
  const status = toStatus(view)
  const facets = useFacets("quotes", { view: scope })
  const packs = usePacks()
  const filters = useMemo(() => {
    const name = (id: string) => packs.data?.find((p) => p.id === id)?.name ?? id
    return quoteFilters(facets.data, name)
  }, [facets.data, packs.data])
  const lv = useListView<QuoteItem>({
    entity: "quotes",
    page: "quotes",
    rows: [],
    filters,
    csv: quoteCsv,
    columns: TOGGLEABLE,
    exportName: "报价单",
    server: {
      total: () => query.data?.total,
      fetchAll: (p) => fetchAllPages<QuoteItem>("/api/quotes", { view: scope, status, ...serverQuery(p) }),
    },
  })
  const query = useQuotes({ view: scope, status, page: lv.pageNo, page_size: PAGE_SIZE }, true, lv.params)
  const rows = useMemo(() => query.data?.items ?? [], [query.data])
  const columns = useMemo(() => quoteColumns.filter((c) => !lv.hidden.includes(c.id)), [lv.hidden])
  const filtered = Object.keys(lv.bar.activeFilters).length > 0
  const sel = useRowSelection(rows, quoteId)
  const toPage = (n: number) => {
    sel.clear()
    lv.setPageNo(n)
  }

  return (
    <PageFrame
      title="报价单"
      icon={FileText}
      actions={
        <>
          {canCreate ? <FrameAction icon={Plus} label="新建报价" href="/quotes/new" /> : null}
          {canAiWrite ? <FrameAction icon={Sparkles} label="AI 出方案" href="/ai" primary /> : null}
        </>
      }
    >
      {sel.count ? (
        <BulkBar count={sel.count} onExport={() => lv.exportRows(sel.selected)} onClear={sel.clear} />
      ) : (
        <ViewBar
          views={VIEWS}
          value={view}
          onValueChange={(v) => {
            setView(v)
            toPage(1)
          }}
          count={query.data?.total}
          list={lv.bar}
        />
      )}
      <PageTip id="quotes" className="mx-3 mt-2">
        {PAGE_TIPS.quotes}
      </PageTip>
      {query.isError && !query.data ? (
        <QueryError
          error={query.error}
          onRetry={() => void query.refetch()}
          retrying={query.isFetching}
          feature="报价单"
        />
      ) : (
        <DataGrid
          columns={columns}
          data={rows}
          getRowId={quoteId}
          selection={sel.selection}
          onSelectionChange={sel.setSelection}
          loading={query.isPending}
          total={query.data?.total}
          pagination={{ page: lv.pageNo, pageSize: PAGE_SIZE, onPageChange: toPage }}
          empty={
            filtered ? (
              <EmptyState icon={FileText} title="没有符合筛选条件的报价单" description="可以在上方清除筛选。" />
            ) : (
              <EmptyState
                icon={FileText}
                title={
                  view === "all" ? "还没有报价单" : `没有「${VIEWS.find((v) => v.value === view)?.label}」的报价单`
                }
                description="让 AI 按客户需求出方案，或点右上角「新建报价」自己从产品目录选物料。"
                action={
                  canAiWrite ? (
                    <Button size="sm" asChild>
                      <Link href="/ai">
                        <Sparkles />
                        AI 出方案
                      </Link>
                    </Button>
                  ) : undefined
                }
              />
            )
          }
        />
      )}
    </PageFrame>
  )
}
