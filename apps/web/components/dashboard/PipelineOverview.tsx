"use client"

import { Skeleton } from "@/components/ui/skeleton"
import { usePipelineSummary } from "@/hooks/useOpportunities"
import { isNotImplemented } from "@/lib/errors"
import { formatFen } from "@/lib/format"
import type { DataView } from "@/types/api"

/**
 * 管道概览：总金额与加权金额（GET /api/pipeline/summary）。
 * 原型此处是 TaskList，但契约没有任务接口，先用管道数据代替（见汇报）。
 */
export function PipelineOverview({ view }: { view: DataView }) {
  const query = usePipelineSummary(view)
  const s = query.data
  const rows = [
    { label: "管道总金额", value: s ? formatFen(s.total_amount) : "—" },
    { label: "加权金额", value: s ? formatFen(s.weighted_amount) : "—", hint: "Σ 金额 × 赢率" },
    { label: "商机数", value: s ? String(s.stages.reduce((n, x) => n + x.count, 0)) : "—" },
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
