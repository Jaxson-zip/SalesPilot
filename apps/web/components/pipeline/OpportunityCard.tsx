"use client"

import { useDraggable } from "@dnd-kit/core"
import { Building2, Calendar, Coins, User } from "lucide-react"

import { Chip } from "@/components/biz/Chip"
import { formatFen } from "@/lib/format"
import { isFinalStage } from "@/lib/pipeline"
import { cn } from "@/lib/utils"
import type { OpportunityItem } from "@/types/api"

/** 预计成交日：YYYY-MM-DD → MM-DD（同年）/ 原样 */
function shortDate(d: string | null): string {
  if (!d) return "未设置"
  const year = String(new Date().getFullYear())
  return d.startsWith(year) ? d.slice(5, 10) : d.slice(0, 10)
}

/** OpportunityCard：标题 + 客户 / 金额 / 预计成交 / 负责人 */
export function OpportunityCardBody({
  opp,
  onOpen,
  className,
}: {
  opp: OpportunityItem
  onOpen?: () => void
  className?: string
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter") onOpen?.()
      }}
      className={cn(
        "min-w-0 cursor-pointer rounded-lg border border-zinc-200 bg-white p-2.5 outline-none hover:border-zinc-300 hover:shadow-sm focus-visible:ring-2 focus-visible:ring-zinc-300",
        className,
      )}
    >
      <div className="mb-2 truncate font-medium" title={opp.name}>
        {opp.name}
      </div>
      <div className="space-y-1.5 text-zinc-600">
        <div className="flex min-w-0 items-center gap-2 overflow-hidden">
          <Building2 className="size-3.5 shrink-0 text-zinc-400" />
          <span className="min-w-0 truncate">
            <Chip name={opp.customer.name} logo={opp.customer.name.slice(0, 1)} />
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Coins className="size-3.5 shrink-0 text-zinc-400" />
          <span className="tabular-nums">{formatFen(opp.amount)}</span>
          <span className="text-xs text-zinc-400 tabular-nums">· {opp.win_rate}%</span>
        </div>
        <div className="flex items-center gap-2">
          <Calendar className="size-3.5 shrink-0 text-zinc-400" />
          {shortDate(opp.expected_close_date)}
        </div>
        <div className="flex min-w-0 items-center gap-2">
          <User className="size-3.5 shrink-0 text-zinc-400" />
          <Chip name={opp.owner.name} />
        </div>
      </div>
    </div>
  )
}

/** 可拖拽卡片（终态商机不能拖） */
export function DraggableOpportunityCard({ opp, onOpen }: { opp: OpportunityItem; onOpen: () => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: opp.id,
    data: { stage: opp.stage },
    disabled: isFinalStage(opp.stage),
  })
  return (
    <div ref={setNodeRef} {...attributes} {...listeners} className={cn("touch-none", isDragging && "opacity-40")}>
      <OpportunityCardBody opp={opp} onOpen={onOpen} />
    </div>
  )
}
