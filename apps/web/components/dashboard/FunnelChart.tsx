import { ArrowRight } from "lucide-react"
import Link from "next/link"

import { Skeleton } from "@/components/ui/skeleton"
import { formatFen } from "@/lib/format"
import { STAGE_META } from "@/lib/labels"
import { funnelWidths, normalizeFunnel } from "@/lib/pipeline"
import type { FunnelStage, OpportunityStage } from "@/types/api"

/** 漏斗条颜色（与原型 FunnelChart 一致） */
const BAR: Record<OpportunityStage, string> = {
  lead: "bg-zinc-400",
  qualified: "bg-blue-400",
  proposal: "bg-violet-400",
  negotiation: "bg-orange-400",
  won: "bg-emerald-500",
  lost: "bg-red-400",
}

export function FunnelChart({ stages, loading }: { stages: FunnelStage[] | undefined; loading?: boolean }) {
  const rows = normalizeFunnel(stages ?? [])
  const widths = funnelWidths(rows)
  const won = rows.find((s) => s.stage === "won")
  return (
    <div className="min-w-0 rounded-lg border border-zinc-200 lg:col-span-2">
      <div className="flex h-10 items-center justify-between border-b border-zinc-100 px-4">
        <span className="font-medium">销售漏斗</span>
        <Link href="/pipeline" className="inline-flex items-center gap-1 text-zinc-500 hover:text-zinc-900">
          看板
          <ArrowRight className="size-3.5" />
        </Link>
      </div>
      <div className="space-y-3 p-4">
        {rows.map((s, i) => (
          <div key={s.stage} className="flex items-center gap-3">
            <span className="w-16 shrink-0 text-zinc-500">{STAGE_META[s.stage].label}</span>
            <div className="h-2 min-w-0 flex-1 rounded-full bg-zinc-100">
              {loading ? null : (
                <div className={`h-2 rounded-full ${BAR[s.stage]}`} style={{ width: `${widths[i]}%` }} />
              )}
            </div>
            {loading ? (
              <Skeleton className="h-3.5 w-20" />
            ) : (
              <>
                <span className="w-6 shrink-0 text-right tabular-nums">{s.count}</span>
                <span className="w-24 shrink-0 truncate text-right text-zinc-500 tabular-nums">
                  {formatFen(s.amount)}
                </span>
              </>
            )}
          </div>
        ))}
        {!loading && won?.unsigned_count ? (
          <p className="text-xs text-amber-700">
            赢单里有 {won.unsigned_count} 个还没签合同（{formatFen(won.unsigned_amount ?? 0)}），不计入本月成交
          </p>
        ) : null}
      </div>
    </div>
  )
}
