"use client"

import { FileText, Sparkles } from "lucide-react"
import Link from "next/link"
import { useMemo, useState } from "react"

import { DataGrid } from "@/components/biz/DataGrid"
import { EmptyState } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { ViewBar, type ViewOption } from "@/components/biz/ViewBar"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { useListView } from "@/hooks/useListView"
import { usePermissions } from "@/hooks/usePermissions"
import { usePacks } from "@/hooks/useProductLines"
import { useQuotes } from "@/hooks/useQuotes"
import { QUOTE_STATUS_META } from "@/lib/labels"
import { defaultScope } from "@/lib/views"
import type { QuoteStatus } from "@/types/api"

import { quoteColumns, quoteCsv, quoteFilters, quoteSort } from "./columns"

const STATUS_VIEWS: QuoteStatus[] = ["draft", "pending_approval", "approved", "sent", "accepted", "rejected"]
const VIEWS: ViewOption[] = [
  { value: "all", label: "所有报价单" },
  ...STATUS_VIEWS.map((s) => ({ value: s, label: QUOTE_STATUS_META[s].label })),
]

function toStatus(v: string): QuoteStatus | undefined {
  return STATUS_VIEWS.find((s) => s === v)
}

const TOGGLEABLE = quoteColumns.slice(1).map((c) => ({ id: c.id, label: c.label }))

/** 报价单列表：按状态切换视图；数据范围跟随角色（销售本人 / 主管团队 / 管理员全部） */
export default function QuotesPage() {
  const { role } = useSession()
  const { canAiWrite } = usePermissions()
  const [view, setView] = useState("all")
  // 视图里的状态走接口参数；其余筛选 / 排序在前端对已加载数据处理
  const query = useQuotes({ view: defaultScope(role), status: toStatus(view), page: 1, page_size: 100 })
  const packs = usePacks()
  const all = useMemo(() => query.data?.items ?? [], [query.data])
  const filters = useMemo(() => {
    const name = (id: string) => packs.data?.find((p) => p.id === id)?.name ?? id
    return quoteFilters(all, name)
  }, [all, packs.data])
  const lv = useListView({
    page: "quotes",
    rows: all,
    filters,
    sort: quoteSort,
    csv: quoteCsv,
    columns: TOGGLEABLE,
    exportName: "报价单",
  })
  const columns = useMemo(() => quoteColumns.filter((c) => !lv.hidden.includes(c.id)), [lv.hidden])
  const filtered = Object.keys(lv.bar.activeFilters).length > 0

  return (
    <PageFrame
      title="报价单"
      icon={FileText}
      actions={canAiWrite ? <FrameAction icon={Sparkles} label="AI 出方案" href="/ai" primary /> : null}
    >
      <ViewBar
        views={VIEWS}
        value={view}
        onValueChange={setView}
        count={filtered ? lv.rows.length : query.data?.total}
        list={lv.bar}
      />
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
          data={lv.rows}
          getRowId={(q) => q.id}
          loading={query.isPending}
          total={filtered ? lv.rows.length : query.data?.total}
          empty={
            filtered ? (
              <EmptyState icon={FileText} title="没有符合筛选条件的报价单" description="可以在上方清除筛选。" />
            ) : (
              <EmptyState
                icon={FileText}
                title={
                  view === "all" ? "还没有报价单" : `没有「${VIEWS.find((v) => v.value === view)?.label}」的报价单`
                }
                description="报价单由 AI 方案工作台生成：描述客户需求，AI 会按行业包出方案并计算价格与毛利。"
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
