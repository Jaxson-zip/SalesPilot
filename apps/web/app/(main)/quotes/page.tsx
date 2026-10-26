"use client"

import { Boxes, Building2, CircleDot, FileText, Percent, Sparkles } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { DataGrid } from "@/components/biz/DataGrid"
import { EmptyState } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { ViewBar, type ViewOption } from "@/components/biz/ViewBar"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { useQuotes } from "@/hooks/useQuotes"
import { QUOTE_STATUS_META } from "@/lib/labels"
import { defaultScope } from "@/lib/views"
import type { QuoteStatus } from "@/types/api"

import { quoteColumns } from "./columns"

const FILTER_FIELDS = [
  { label: "状态", icon: CircleDot },
  { label: "客户", icon: Building2 },
  { label: "毛利率", icon: Percent },
  { label: "行业包", icon: Boxes },
]

const STATUS_VIEWS: QuoteStatus[] = ["draft", "pending_approval", "approved", "sent", "accepted", "rejected"]
const VIEWS: ViewOption[] = [
  { value: "all", label: "所有报价单" },
  ...STATUS_VIEWS.map((s) => ({ value: s, label: QUOTE_STATUS_META[s].label })),
]

function toStatus(v: string): QuoteStatus | undefined {
  return STATUS_VIEWS.find((s) => s === v)
}

/** 报价单列表：按状态切换视图；数据范围跟随角色（销售本人 / 主管团队 / 管理员全部） */
export default function QuotesPage() {
  const { role } = useSession()
  const [view, setView] = useState("all")
  const query = useQuotes({ view: defaultScope(role), status: toStatus(view), page: 1, page_size: 50 })

  return (
    <PageFrame
      title="报价单"
      icon={FileText}
      actions={<FrameAction icon={Sparkles} label="AI 出方案" href="/ai" primary />}
    >
      <ViewBar views={VIEWS} value={view} onValueChange={setView} count={query.data?.total} fields={FILTER_FIELDS} />
      {query.isError && !query.data ? (
        <QueryError
          error={query.error}
          onRetry={() => void query.refetch()}
          retrying={query.isFetching}
          feature="报价单"
        />
      ) : (
        <DataGrid
          columns={quoteColumns}
          data={query.data?.items ?? []}
          getRowId={(q) => q.id}
          loading={query.isPending}
          total={query.data?.total}
          empty={
            <EmptyState
              icon={FileText}
              title={view === "all" ? "还没有报价单" : `没有「${VIEWS.find((v) => v.value === view)?.label}」的报价单`}
              description="报价单由 AI 方案工作台生成：描述客户需求，AI 会按行业包出方案并计算价格与毛利。"
              action={
                <Button size="sm" asChild>
                  <Link href="/ai">
                    <Sparkles />
                    AI 出方案
                  </Link>
                </Button>
              }
            />
          }
        />
      )}
    </PageFrame>
  )
}
