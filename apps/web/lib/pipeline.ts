/** 商机看板的纯函数：分组、阶段切换的乐观更新、拖拽目标校验、漏斗宽度 */
import { STAGE_ORDER } from "@/lib/labels"
import type { FunnelStage, OpportunityItem, OpportunityStage, Paged } from "@/types/api"

/** 看板五列（输单不占列，拖到底部「输单」区域） */
export const KANBAN_STAGES: OpportunityStage[] = STAGE_ORDER

export const FINAL_STAGES: OpportunityStage[] = ["won", "lost"]

export function isFinalStage(stage: OpportunityStage): boolean {
  return FINAL_STAGES.includes(stage)
}

export function isStage(v: unknown): v is OpportunityStage {
  return typeof v === "string" && (STAGE_ORDER as string[]).concat("lost").includes(v)
}

export type StageGroups = Record<OpportunityStage, OpportunityItem[]>

export function groupByStage(items: OpportunityItem[]): StageGroups {
  const groups: StageGroups = { lead: [], qualified: [], proposal: [], negotiation: [], won: [], lost: [] }
  for (const it of items) groups[it.stage]?.push(it)
  return groups
}

export function sumAmount(items: OpportunityItem[]): number {
  return items.reduce((s, it) => s + it.amount, 0)
}

export type StageMoveCheck = { ok: true } | { ok: false; reason: string }

/** 前端预校验（真正的规则在 core：终态不能再切换 → 42201 opportunity_stage_final） */
export function checkStageMove(from: OpportunityStage, to: OpportunityStage): StageMoveCheck {
  if (from === to) return { ok: false, reason: "阶段未变化" }
  if (isFinalStage(from)) return { ok: false, reason: "赢单 / 输单为终态，不能再切换阶段" }
  return { ok: true }
}

/** 乐观更新：把列表里的某条商机改成新阶段（返回新对象，不修改原数据） */
export function applyStageChange(
  page: Paged<OpportunityItem> | undefined,
  id: string,
  stage: OpportunityStage,
  now: Date = new Date(),
): Paged<OpportunityItem> | undefined {
  if (!page) return page
  let changed = false
  const items = page.items.map((it) => {
    if (it.id !== id) return it
    changed = true
    return { ...it, stage, updated_at: now.toISOString() }
  })
  return changed ? { ...page, items } : page
}

/** 漏斗条宽度：按数量相对最大值取百分比，最少 4% 以便看得到 */
export function funnelWidths(stages: FunnelStage[]): number[] {
  const max = Math.max(0, ...stages.map((s) => s.count))
  if (max === 0) return stages.map(() => 0)
  return stages.map((s) => (s.count === 0 ? 0 : Math.max(4, Math.round((s.count / max) * 100))))
}

/** 漏斗只展示推进顺序里的阶段，并按顺序补齐缺失阶段 */
export function normalizeFunnel(stages: FunnelStage[]): FunnelStage[] {
  return STAGE_ORDER.map((stage) => stages.find((s) => s.stage === stage) ?? { stage, count: 0, amount: 0 })
}

/** 阶段条：当前阶段之前 = done，当前 = current，之后 = todo；输单时全部为 todo */
export function stageBarState(current: OpportunityStage, stage: OpportunityStage): "done" | "current" | "todo" {
  if (current === stage) return "current"
  if (current === "lost") return "todo"
  return STAGE_ORDER.indexOf(stage) < STAGE_ORDER.indexOf(current) ? "done" : "todo"
}
