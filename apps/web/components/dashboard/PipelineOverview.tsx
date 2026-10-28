"use client"

import { Skeleton } from "@/components/ui/skeleton"
import { usePipelineSummary } from "@/hooks/useOpportunities"
import { isNotImplemented } from "@/lib/errors"
import { formatFen } from "@/lib/format"
import type { DataView } from "@/types/api"

/**
 * 管道概览（GET /api/pipeline/summary）：只算进行中的商机，赢单、输单不计入，
 * 与左边指标卡「进行中商机 · 预计」口径一致。
 */
export function PipelineOverview({ view }: { view: DataView }) {
  const query = usePipelineSummary(view)
  const s = query.data
  const rows = [
    { label: "进行中金额", value: s ? formatFen(s.total_amount) : "—" },
    { label: "加权金额", value: s ? formatFen(s.weighted_amount) : "—", hint: "Σ 金额 × 赢率" },
    { label: "进行中商机", value: s ? String(s.open_count) : "—" },
  ]
  return (
    <div className="min-w-0 rounded-lg border border-zinc-200">
      <div className="flex h-10 items-center border-b border-zinc-100 px-4 font-medium">管道概览</div>
      <div className="p-1.5">
        {query.isError ? (
          <div className="px-2.5 py-6 text-center text-zinc-500">
            {isNotImplemented(query.error) ? "后端开发中" : "加载失败"}
          </div>
        ) : (
          rows.map((r) => (
            <div key={r.label} className="flex h-10 items-center justify-between gap-3 rounded-md px-2.5">
              <span className="truncate text-zinc-500">
                {r.label}
                {r.hint ? <span className="ml-1.5 text-xs text-zinc-400">{r.hint}</span> : null}
              </span>
              {query.isPending ? (
                <Skeleton className="h-4 w-20" />
              ) : (
                <span className="font-medium tabular-nums">{r.value}</span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
