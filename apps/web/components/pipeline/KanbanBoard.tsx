"use client"

import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core"
import { CircleX, Plus } from "lucide-react"
import { useState, type ReactNode } from "react"

import { Tag } from "@/components/biz/Tag"
import { Skeleton } from "@/components/ui/skeleton"
import { DraggableOpportunityCard, OpportunityCardBody } from "@/components/pipeline/OpportunityCard"
import { formatFen } from "@/lib/format"
import { STAGE_META } from "@/lib/labels"
import { isStage, KANBAN_STAGES, sumAmount, type StageGroups } from "@/lib/pipeline"
import { cn } from "@/lib/utils"
import type { OpportunityItem, OpportunityStage } from "@/types/api"

interface BoardProps {
  groups: StageGroups
  loading?: boolean
  onOpen: (opp: OpportunityItem) => void
  /** 不传表示无权新建（不显示「新建」） */
  onCreate?: () => void
  /** 能否拖动这张卡片（只有负责人本人能切换阶段） */
  canDrag: (opp: OpportunityItem) => boolean
  /** 拖拽到某阶段（含 lost） */
  onMove: (opp: OpportunityItem, to: OpportunityStage) => void
}

function Column({ stage, children }: { stage: OpportunityStage; children: ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: stage })
  return (
    <div
      ref={setNodeRef}
      className={cn("min-h-40 min-w-0 rounded-lg p-1 transition-colors", isOver && "bg-zinc-100")}
      data-stage={stage}
    >
      {children}
    </div>
  )
}

/** 空列占位：可拖拽时提示「拖到这里」，否则只说明暂无商机 */
function EmptyColumn({ droppable }: { droppable: boolean }) {
  return (
    <div className="flex h-20 items-center justify-center rounded-lg border border-dashed border-zinc-200 text-xs text-zinc-400">
      {droppable ? "拖到这里" : "暂无商机"}
    </div>
  )
}

function LostZone({ visible }: { visible: boolean }) {
  const { setNodeRef, isOver } = useDroppable({ id: "lost" })
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "sticky bottom-0 mt-3 flex h-12 items-center justify-center gap-1.5 rounded-lg border border-dashed text-zinc-500 transition-all",
        visible ? "opacity-100" : "pointer-events-none opacity-0",
        isOver ? "border-red-400 bg-red-50 text-red-700" : "border-zinc-300 bg-white",
      )}
    >
      <CircleX className="size-4" />
      拖到这里标记为「{STAGE_META.lost.label}」
    </div>
  )
}

/** ≥1024：五列等分看板（dnd-kit 拖拽切换阶段，不横向滚动） */
export function KanbanBoard({ groups, loading, onOpen, onCreate, canDrag, onMove }: BoardProps) {
  const [active, setActive] = useState<OpportunityItem | null>(null)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    // 空格开始 / 结束键盘拖拽；Enter 留给「打开详情」
    useSensor(KeyboardSensor, { keyboardCodes: { start: ["Space"], cancel: ["Escape"], end: ["Space"] } }),
  )
  const all = KANBAN_STAGES.flatMap((s) => groups[s])
  const anyDraggable = all.some(canDrag)

  const onDragStart = (e: DragStartEvent) => setActive(all.find((o) => o.id === e.active.id) ?? null)
  const onDragEnd = (e: DragEndEvent) => {
    setActive(null)
    const opp = all.find((o) => o.id === e.active.id)
    const to = e.over?.id
    if (opp && isStage(to) && to !== opp.stage) onMove(opp, to)
  }

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setActive(null)}>
      <div className="grid grid-cols-5 gap-3">
        {KANBAN_STAGES.map((stage) => (
          <div key={stage} className="min-w-0">
            <div className="mb-1 flex h-8 items-center gap-1.5 px-1">
              <Tag color={STAGE_META[stage].color}>{STAGE_META[stage].label}</Tag>
              <span className="text-zinc-400 tabular-nums">{groups[stage].length}</span>
              <span className="min-w-0 flex-1 truncate text-right text-xs text-zinc-400 tabular-nums">
                {groups[stage].length ? formatFen(sumAmount(groups[stage])) : ""}
              </span>
            </div>
            <Column stage={stage}>
              <div className="space-y-2">
                {loading
                  ? [0, 1].map((i) => <Skeleton key={i} className="h-[118px] w-full rounded-lg" />)
                  : groups[stage].map((o) => (
                      <DraggableOpportunityCard key={o.id} opp={o} draggable={canDrag(o)} onOpen={() => onOpen(o)} />
                    ))}
                {!loading && groups[stage].length === 0 ? <EmptyColumn droppable={anyDraggable} /> : null}
                {stage === "lead" && onCreate ? (
                  <button
                    type="button"
                    onClick={onCreate}
                    className="inline-flex h-8 w-full items-center gap-1.5 rounded-md px-2 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
                  >
                    <Plus className="size-3.5" />
                    新建
                  </button>
                ) : null}
              </div>
            </Column>
          </div>
        ))}
      </div>
      <LostZone visible={active !== null} />
      <DragOverlay>{active ? <OpportunityCardBody opp={active} className="shadow-lg" /> : null}</DragOverlay>
    </DndContext>
  )
}
