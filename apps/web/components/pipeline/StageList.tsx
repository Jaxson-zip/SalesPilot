"use client"

import { Plus } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import { OpportunityCardBody } from "@/components/pipeline/OpportunityCard"
import { formatFen } from "@/lib/format"
import { STAGE_META } from "@/lib/labels"
import { KANBAN_STAGES, sumAmount, type StageGroups } from "@/lib/pipeline"
import { cn } from "@/lib/utils"
import type { OpportunityItem, OpportunityStage } from "@/types/api"

/** <1024：顶部阶段切换（可换行，不滚动）+ 当前阶段的卡片纵向排列；切换阶段在商机 Sheet 里操作 */
export function StageList({
  groups,
  loading,
  stage,
  onStageChange,
  onOpen,
  onCreate,
  showOwner = true,
}: {
  groups: StageGroups
  loading?: boolean
  stage: OpportunityStage
  onStageChange: (s: OpportunityStage) => void
  onOpen: (opp: OpportunityItem) => void
  /** 不传表示无权新建 */
  onCreate?: () => void
  showOwner?: boolean
}) {
  const list = groups[stage]
  return (
    <>
      <div className="sticky top-0 z-10 flex flex-wrap gap-1.5 border-b border-zinc-100 bg-white px-3 py-2.5">
        {KANBAN_STAGES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onStageChange(s)}
            className={cn(
              "inline-flex h-7 items-center gap-1 rounded-full px-2.5 text-xs",
              s === stage ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200",
            )}
          >
            {STAGE_META[s].label}
            <span className={cn("tabular-nums", s === stage ? "text-white/70" : "text-zinc-400")}>
              {groups[s].length}
            </span>
          </button>
        ))}
      </div>
      <div className="space-y-2 p-3">
        <div className="px-0.5 text-zinc-500">
          {STAGE_META[stage].label} · 合计{" "}
          <span className="text-zinc-800 tabular-nums">{formatFen(sumAmount(list))}</span>
        </div>
        {loading
          ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-[118px] w-full rounded-lg" />)
          : list.map((o) => <OpportunityCardBody key={o.id} opp={o} onOpen={() => onOpen(o)} showOwner={showOwner} />)}
        {!loading && list.length === 0 ? <div className="py-6 text-center text-zinc-400">该阶段暂无商机</div> : null}
        {onCreate ? (
          <button
            type="button"
            onClick={onCreate}
            className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-zinc-300 text-zinc-500 hover:bg-zinc-50"
          >
            <Plus className="size-3.5" />
            新建商机
          </button>
        ) : null}
      </div>
    </>
  )
}
