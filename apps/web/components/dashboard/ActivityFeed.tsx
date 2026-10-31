"use client"

import { Eye, History } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { LetterAvatar } from "@/components/biz/Chip"
import { EmptyState } from "@/components/biz/EmptyState"
import { QueryError } from "@/components/biz/QueryStatus"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useActivities } from "@/hooks/useDashboard"
import { formatRelative } from "@/lib/format"
import { activityActionLabel } from "@/lib/labels"
import { subjectHref } from "@/lib/links"
import { activityActor } from "@/lib/timeline"
import type { Activity, DataView } from "@/types/api"

const SUBJECT_LABEL: Record<string, string> = {
  customer: "客户",
  opportunity: "商机",
  quote: "报价单",
  expense: "报销",
  contract: "合同",
  approval: "审批",
}

/** 先取 20 条，卡片内滚动（不把整页撑长）；到底部可以「加载更多」 */
const PAGE = 20
const MAX = 100

/** 「哪一单」：名称或编号，能打开的做成链接 */
function SubjectName({ a }: { a: Activity }) {
  if (!a.subject_name) return null
  const href = subjectHref(a.subject_type, a.subject_id)
  if (!href) return <span className="min-w-0 truncate">{a.subject_name}</span>
  return (
    <Link href={href} className="min-w-0 truncate text-zinc-900 hover:underline">
      {a.subject_name}
    </Link>
  )
}

function FeedRow({ a }: { a: Activity }) {
  const by = activityActor(a)
  const isAi = by === "ai"
  const name = by === "system" ? "系统" : isAi ? "AI 助手" : (a.actor?.name ?? "—")
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
          <SubjectName a={a} />
        </div>
        {a.content ? (
          <div className="mt-0.5 line-clamp-2 break-words text-zinc-600" title={a.content}>
            {a.content}
          </div>
        ) : null}
      </div>
      <span className="shrink-0 text-xs text-zinc-400">{formatRelative(a.created_at)}</span>
    </li>
  )
}

/** 动态流：销售「我的动态」，主管 / 管理员「团队动态」（可见范围由 core 按数据权限过滤） */
export function ActivityFeed({ view, isLead, scope }: { view: DataView; isLead: boolean; scope: string }) {
  const [limit, setLimit] = useState(PAGE)
  const query = useActivities({ view, limit })
  const items = query.data ?? []
  const title = isLead ? "团队动态" : "我的动态"
  const more = items.length >= limit && limit < MAX
  return (
    <div className="flex min-w-0 flex-col rounded-lg border border-zinc-200">
      <div className="flex h-10 shrink-0 items-center gap-2 border-b border-zinc-100 px-4">
        <span className="shrink-0 font-medium">{title}</span>
        <span className="inline-flex min-w-0 items-center gap-1 truncate text-xs text-zinc-400">
          <Eye className="size-3.5 shrink-0" />
          <span className="truncate">{isLead ? `可见范围：${scope}` : "仅你负责的客户和商机"}</span>
        </span>
      </div>
      <div className="max-h-[26rem] overflow-y-auto px-4 py-1">
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
          <>
            <ul aria-label={title}>
              {items.map((a) => (
                <FeedRow key={a.id} a={a} />
              ))}
            </ul>
            {more ? (
              <div className="py-2 text-center">
                <Button
                  variant="ghost"
                  size="xs"
                  className="text-zinc-500"
                  disabled={query.isFetching}
                  onClick={() => setLimit((n) => Math.min(n + PAGE, MAX))}
                >
                  {query.isFetching ? "加载中…" : "加载更多"}
                </Button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}
