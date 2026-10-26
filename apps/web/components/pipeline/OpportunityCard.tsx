"use client"

import { useDraggable, type DraggableAttributes, type DraggableSyntheticListeners } from "@dnd-kit/core"
import { Building2, Calendar, CalendarClock, Coins, User } from "lucide-react"
import type { KeyboardEvent } from "react"

import { Chip } from "@/components/biz/Chip"
import { Tag } from "@/components/biz/Tag"
import { formatFen } from "@/lib/format"
import { expectedCloseText, isFinalStage } from "@/lib/pipeline"
import { nextStepView, staleText } from "@/lib/tasks"
import { cn } from "@/lib/utils"
import type { OpportunityItem } from "@/types/api"

/** 下一步（v3 §12）：有任务显示「下一步：xxx · 明天」，逾期红色；未终态且没有任务显示淡黄色提示 */
function NextStepLine({ opp }: { opp: OpportunityItem }) {
  const v = nextStepView(opp)
  if (v.kind === "hidden") return null
  if (v.kind === "missing")
    return <div className="mt-2 rounded bg-amber-50 px-1.5 py-1 text-xs text-amber-800">未安排下一步</div>
  return (
    <div className={cn("mt-2 flex min-w-0 items-center gap-1.5 text-xs", v.overdue ? "text-red-600" : "text-zinc-600")}>
      <CalendarClock className="size-3.5 shrink-0" />
      <span className="truncate" title={v.text}>
        {v.text}
      </span>
    </div>
  )
}

interface DragBinding {
  setNodeRef: (el: HTMLElement | null) => void
  attributes: DraggableAttributes
  listeners: DraggableSyntheticListeners
  isDragging: boolean
}

/**
 * OpportunityCard：标题 + 客户 / 金额 · 赢率 / 预计成交 / 负责人（「我的」视图隐藏）/ 下一步 / 停滞提醒。
 * 整张卡片只有一层可点击元素（role=button）：Enter / 点击打开详情；可拖拽时同一元素上挂拖拽监听，空格开始键盘拖拽。
 */
export function OpportunityCardBody({
  opp,
  onOpen,
  className,
  drag,
  showOwner = true,
}: {
  opp: OpportunityItem
  onOpen?: () => void
  className?: string
  drag?: DragBinding
  /** 「我的商机」视图里负责人都是自己，不显示（U8） */
  showOwner?: boolean
}) {
  const stale = staleText(opp)
  const dndKeyDown = drag?.listeners?.onKeyDown as ((e: KeyboardEvent<HTMLDivElement>) => void) | undefined
  return (
    <div
      ref={drag?.setNodeRef}
      {...drag?.attributes}
      {...drag?.listeners}
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (drag?.isDragging) return dndKeyDown?.(e)
        if (e.key === "Enter" || (!drag && e.key === " ")) {
          e.preventDefault()
          return onOpen?.()
        }
        dndKeyDown?.(e)
      }}
      className={cn(
        "min-w-0 cursor-pointer rounded-lg border border-zinc-200 bg-white p-2.5 outline-none select-none hover:border-zinc-300 hover:shadow-sm focus-visible:ring-2 focus-visible:ring-zinc-300",
        drag && "touch-none",
        drag?.isDragging && "opacity-40",
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
        <div className="flex items-center gap-2" title="预计成交日期">
          <Calendar className="size-3.5 shrink-0 text-zinc-400" />
          {expectedCloseText(opp.expected_close_date)}
        </div>
        {showOwner ? (
          <div className="flex min-w-0 items-center gap-2">
            <User className="size-3.5 shrink-0 text-zinc-400" />
            <Chip name={opp.owner.name} />
          </div>
        ) : null}
      </div>
      <NextStepLine opp={opp} />
      {stale ? (
        <div className="mt-2">
          <Tag color="orange">{stale}</Tag>
        </div>
      ) : null}
    </div>
  )
}

function DraggableCard({ opp, onOpen, showOwner }: { opp: OpportunityItem; onOpen: () => void; showOwner: boolean }) {
  const drag = useDraggable({ id: opp.id, data: { stage: opp.stage } })
  return <OpportunityCardBody opp={opp} onOpen={onOpen} drag={drag} showOwner={showOwner} />
}

/** 看板卡片：终态商机、非本人负责的商机不能拖，直接渲染卡片本体（不包拖拽层） */
export function DraggableOpportunityCard({
  opp,
  draggable,
  onOpen,
  showOwner = true,
}: {
  opp: OpportunityItem
  draggable: boolean
  onOpen: () => void
  showOwner?: boolean
}) {
  if (!draggable || isFinalStage(opp.stage))
    return <OpportunityCardBody opp={opp} onOpen={onOpen} showOwner={showOwner} />
  return <DraggableCard opp={opp} onOpen={onOpen} showOwner={showOwner} />
}
