"use client"

import { useState, type ReactElement } from "react"
import { toast } from "sonner"

import { LostReasonDialog } from "@/components/pipeline/LostReasonDialog"
import { WonDialog } from "@/components/pipeline/WonDialog"
import { useChangeStage } from "@/hooks/useOpportunities"
import { STAGE_META } from "@/lib/labels"
import {
  canUndoStage,
  planStageMove,
  stageChangedText,
  stageUndoneText,
  UNDO_DURATION_MS,
  UNDO_LABEL,
} from "@/lib/stage-move"
import type { OpportunityItem, OpportunityStage } from "@/types/api"

/**
 * 阶段切换（阶段条、看板拖拽共用）：可逆的立即生效并提供「撤销」；赢单先确认；输单先填原因。
 * dialogs 需要渲染在页面里（确认对话框 + 输单原因弹窗）。
 */
export function useStageMove(): {
  move: (opp: OpportunityItem, to: OpportunityStage) => void
  changing: boolean
  dialogs: ReactElement
} {
  const change = useChangeStage()
  const [losing, setLosing] = useState<OpportunityItem | null>(null)
  const [winning, setWinning] = useState<OpportunityItem | null>(null)

  const undo = (id: string, movedTo: OpportunityStage, undoTo: OpportunityStage) => {
    if (!canUndoStage(movedTo, undoTo)) return
    change.mutate({ id, stage: undoTo }, { onSuccess: () => toast.success(stageUndoneText(undoTo)) })
  }

  const move = (opp: OpportunityItem, to: OpportunityStage) => {
    const plan = planStageMove(opp.stage, to)
    if (plan.kind === "invalid") return void toast.error(plan.reason)
    if (plan.kind === "lost") return setLosing(opp)
    if (plan.kind === "confirm") return setWinning(opp)
    change.mutate(
      { id: opp.id, stage: to },
      {
        onSuccess: () =>
          toast.success(stageChangedText(to), {
            description: opp.name,
            duration: UNDO_DURATION_MS,
            action: { label: UNDO_LABEL, onClick: () => undo(opp.id, to, plan.undoTo) },
          }),
      },
    )
  }

  const dialogs = (
    <>
      <WonDialog
        opp={winning}
        onCancel={() => setWinning(null)}
        onConfirm={(quote) => {
          if (winning)
            change.mutate(
              { id: winning.id, stage: "won", ...(quote ? { quote_id: quote.id } : {}) },
              {
                onSuccess: () =>
                  toast.success(stageChangedText("won"), {
                    description: quote ? `已按报价 ${quote.code} 生成合同和回款计划` : "未生成合同",
                  }),
              },
            )
          setWinning(null)
        }}
      />
      <LostReasonDialog
        opp={losing}
        onCancel={() => setLosing(null)}
        onConfirm={(reason) => {
          if (losing)
            change.mutate(
              { id: losing.id, stage: "lost", lost_reason: reason },
              { onSuccess: () => toast.success(`已标记为「${STAGE_META.lost.label}」`) },
            )
          setLosing(null)
        }}
      />
    </>
  )
  return { move, changing: change.isPending, dialogs }
}
