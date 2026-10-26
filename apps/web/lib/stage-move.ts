/**
 * 商机阶段切换的防误操作规则（纯函数）：
 * - 非终态之间切换：立即生效 + 8 秒内可撤销（撤销 = 再切回原阶段）
 * - 切到「赢单」：终态，先确认
 * - 切到「输单」：先填原因（LostReasonDialog）
 */
import { STAGE_META } from "@/lib/labels"
import { checkStageMove, isFinalStage } from "@/lib/pipeline"
import type { OpportunityStage } from "@/types/api"

export const UNDO_DURATION_MS = 8000
export const UNDO_LABEL = "撤销"

export type StageMovePlan =
  | { kind: "invalid"; reason: string }
  | { kind: "lost" }
  | { kind: "confirm" }
  | { kind: "direct"; undoTo: OpportunityStage }

export function planStageMove(from: OpportunityStage, to: OpportunityStage): StageMovePlan {
  const check = checkStageMove(from, to)
  if (!check.ok) return { kind: "invalid", reason: check.reason }
  if (to === "lost") return { kind: "lost" }
  if (isFinalStage(to)) return { kind: "confirm" }
  return { kind: "direct", undoTo: from }
}

/** 撤销：只有切换前后都不是终态（且确实发生了变化）时才可撤销 */
export function canUndoStage(movedTo: OpportunityStage, undoTo: OpportunityStage): boolean {
  return !isFinalStage(movedTo) && !isFinalStage(undoTo) && movedTo !== undoTo
}

export function stageChangedText(to: OpportunityStage): string {
  return `已切换到「${STAGE_META[to].label}」`
}

export function stageUndoneText(to: OpportunityStage): string {
  return `已撤销，恢复为「${STAGE_META[to].label}」`
}
