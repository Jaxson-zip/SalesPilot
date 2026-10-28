"use client"

import { ChevronRight, Eye, History } from "lucide-react"
import { useState } from "react"

import { LetterAvatar } from "@/components/biz/Chip"
import { EmptyState } from "@/components/biz/EmptyState"
import { QueryError } from "@/components/biz/QueryStatus"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { useActivities } from "@/hooks/useDashboard"
import { formatRelative } from "@/lib/format"
import { activityActionLabel } from "@/lib/labels"
import type { Activity, DataView } from "@/types/api"

const SUBJECT_LABEL: Record<string, string> = {
  customer: "客户",
  opportunity: "商机",
  quote: "报价单",
  expense: "报销",
  contract: "合同",
  approval: "审批",
}

/** 工作台上只放最近几条，其余在「查看全部」面板里滚动查看，避免把整页撑得很长 */
const PREVIEW = 6
const FULL = 100

function FeedRow({ a, clamp = false }: { a: Activity; clamp?: boolean }) {
  const isAi = a.source === "agent" || a.actor === null
  const name = isAi ? "AI 助手" : (a.actor?.name ?? "—")
  return (
    <li className="flex items-start gap-3 border-b border-zinc-100 py-2.5 last:border-0">
      <LetterAvatar name={isAi ? "AI" : name} className="mt-0.5 size-6 text-[11px]" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-medium">{name}</span>
          <span className="text-zinc-500">{activityActionLabel(a.action, a.subject_type)}</span>
          {SUBJECT_LABEL[a.subject_type] ? (
            <span className="rounded bg-zinc-100 px-1.5 text-xs text-zinc-600">{SUBJECT_LABEL[a.subject_type]}</span>
          ) : null}
        </div>
        {a.content ? (
          <div className={clamp ? "mt-0.5 line-clamp-2 break-words text-zinc-600" : "mt-0.5 break-words text-zinc-600"}>
            {a.content}
          </div>
        ) : null}
      </div>
      <span className="shrink-0 text-xs text-zinc-400">{formatRelative(a.created_at)}</span>
    </li>
  )
}

/** 动态流：销售「我的动态」，主管 / 管理员「团队动态」（可见范围由 core 按数据权限过滤） */
/** 全部动态：右侧面板，列表在面板里滚动 */
function AllActivities({
  open,
  onOpenChange,
  view,
  title,
  scopeText,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  view: DataView
  title: string
  scopeText: string
}) {
  const query = useActivities({ view, limit: FULL }, open)
  const items = query.data ?? []
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 sm:max-w-md">
        <SheetHeader className="border-b border-zinc-100">
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>
            {scopeText} · 最近 {FULL} 条
          </SheetDescription>
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-1">
          {query.isPending ? (
            <Skeleton className="my-3 h-40 w-full" />
          ) : query.isError ? (
            <QueryError
              error={query.error}
              onRetry={() => void query.refetch()}
              retrying={query.isFetching}
              feature="动态"
            />
          ) : (
            <ul aria-label={`全部${title}`}>
              {items.map((a) => (
                <FeedRow key={a.id} a={a} />
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

export function ActivityFeed({ view, isLead, scope }: { view: DataView; isLead: boolean; scope: string }) {
  // 多取一条，用来判断是否还有更多
  const query = useActivities({ view, limit: PREVIEW + 1 })
  const all = query.data ?? []
  const items = all.slice(0, PREVIEW)
  const [open, setOpen] = useState(false)
  const title = isLead ? "团队动态" : "我的动态"
  const scopeText = isLead ? `可见范围：${scope}` : "仅你负责的客户和商机"
  return (
    <div className="min-w-0 rounded-lg border border-zinc-200">
      <div className="flex h-10 items-center gap-2 border-b border-zinc-100 pr-2 pl-4">
        <span className="shrink-0 font-medium">{title}</span>
        <span className="inline-flex min-w-0 flex-1 items-center gap-1 truncate text-xs text-zinc-400">
          <Eye className="size-3.5 shrink-0" />
          <span className="truncate">{scopeText}</span>
        </span>
        {all.length > PREVIEW ? (
          <Button variant="ghost" size="xs" className="shrink-0 text-zinc-500" onClick={() => setOpen(true)}>
            查看全部
            <ChevronRight />
          </Button>
        ) : null}
      </div>
      <AllActivities open={open} onOpenChange={setOpen} view={view} title={title} scopeText={scopeText} />
      <div className="px-4 py-1">
        {query.isPending ? (
          Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="flex gap-3 py-3">
              <Skeleton className="size-6 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3.5 w-1/3" />
                <Skeleton className="h-3.5 w-2/3" />
              </div>
            </div>
          ))
        ) : query.isError ? (
          <QueryError
            error={query.error}
            onRetry={() => void query.refetch()}
            retrying={query.isFetching}
            feature="动态"
          />
        ) : items.length === 0 ? (
          <EmptyState icon={History} title="暂无动态" description="记跟进、推进商机、出报价后，这里会按时间显示。" />
        ) : (
          <ul aria-label={title}>
            {items.map((a) => (
              <FeedRow key={a.id} a={a} clamp />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
