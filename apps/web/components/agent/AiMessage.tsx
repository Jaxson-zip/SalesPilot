"use client"

import { CircleAlert, CornerDownRight, FileText, RotateCcw, Sparkles } from "lucide-react"
import { useState } from "react"

import { ArtifactView } from "@/components/agent/ArtifactView"
import { BomEditor } from "@/components/agent/BomEditor"
import { ChatMarkdown } from "@/components/agent/ChatMarkdown"
import { ConfirmCard, ResultLine } from "@/components/agent/ConfirmCard"
import { MsgActions, type MsgFeedback } from "@/components/agent/MsgActions"
import { PrdDialog } from "@/components/pipeline/PrdDialog"
import { ThinkBlock } from "@/components/agent/ThinkBlock"
import { Button } from "@/components/ui/button"
import { useQuoteDraft } from "@/hooks/useQuoteDraft"
import { useSmoothText } from "@/hooks/useSmoothText"
import { actionResultOf } from "@/lib/action-result"
import { splitFollowUps } from "@/lib/agent-mode"
import type { AgentArtifact, AssistantTurn } from "@/lib/agent-reducer"
import { isCoreTier, isCoreTiers, type CoreSolutionTier } from "@/lib/artifacts"
import { adjustTier, changedQty, type QtyEdits } from "@/lib/bom-adjust"
import { previewRows } from "@/lib/interrupt-preview"
import { cn } from "@/lib/utils"
import type { ResumeDecision } from "@/types/api"

/** 流式出错：错误信息 + 重试（SSE 断开后可恢复） */
function ErrorBanner({
  error,
  onRetry,
  disabled,
}: {
  error: { code: number; message: string }
  onRetry: () => void
  disabled?: boolean
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
      <CircleAlert className="size-4 shrink-0" />
      <span className="min-w-0 flex-1">
        {error.message}（错误码 {error.code}）
      </span>
      <Button variant="outline" size="xs" className="h-7" onClick={onRetry} disabled={disabled}>
        <RotateCcw />
        重试
      </Button>
    </div>
  )
}

/**
 * 一条 AI 回复（不用气泡）：ThinkBlock → 流式正文 → 结构化卡片 → ConfirmCard → MsgActions
 *
 * 正文逐字显示（useSmoothText）；生成中时卡片和确认框等这段话显示完、并且后端停下来（等确认 / 结束）
 * 才出现，避免「卡片一下子全弹出来、文字还在后面打」。
 */
export function AiMessage({
  turn,
  compact,
  busy,
  onDecide,
  onRetry,
  onConfirmRequirement,
  onAsk,
  prdOpportunity,
  readonly,
  feedback,
  draftKey,
}: {
  turn: AssistantTurn
  compact?: boolean
  busy?: boolean
  /** 历史消息：不再响应确认 / 重试 */
  readonly?: boolean
  /** tier：确认生成报价单时另选的档位；items：在物料清单上调整的数量（sku → 数量） */
  onDecide: (decision: ResumeDecision, tier?: string, items?: QtyEdits) => void
  onRetry: () => void
  onConfirmRequirement?: (requirement: Record<string, unknown>) => void
  /** 学习问答：回答末尾「可以接着问」拆成按钮，点击直接发送 */
  onAsk?: (question: string) => void
  /** 会话关联的商机：软件外包方案下面显示「PRD 规格书」（需求清单存在商机上） */
  prdOpportunity?: { id: string; name: string; canGenerate: boolean }
  /** 点赞 / 点踩（会话有 id 后才有） */
  feedback?: MsgFeedback
  /** 待确认方案的调整存本机用的 key（用户 + 会话）；换页、刷新回来能恢复 */
  draftKey?: string | null
}) {
  const [prdOpen, setPrdOpen] = useState(false)
  const live = turn.status === "streaming"
  const tiers = coreTiers(turn.artifacts)
  const actionResult = actionResultOf(turn.artifacts)
  const pending = turn.interrupt?.action === "generate_quote" && !turn.interrupt.decision
  // 生成报价单前可以在三档里另选、改物料数量（每档各自保留）；存本机，换页、刷新回来还在
  const draft = useQuoteDraft(pending && !readonly ? (draftKey ?? null) : null, tiers)
  const { picked, setPicked, editsByTier, setEditsByTier } = draft
  const canPick = pending && !readonly && !busy && tiers.length > 1
  const pickedTier = picked ? tiers.find((t) => t.tier === picked) : undefined
  const canEdit = pending && !readonly && !busy
  const baseTier = pickedTier ?? tiers.find((t) => t.recommended) ?? tiers[0]
  const edits = (baseTier && editsByTier[baseTier.tier]) || {}
  const setEdits = (next: QtyEdits) => {
    if (baseTier) setEditsByTier((m) => ({ ...m, [baseTier.tier]: next }))
  }
  const changes = baseTier ? changedQty(baseTier, edits) : {}
  const adjusted = baseTier && Object.keys(changes).length ? adjustTier(baseTier, edits) : undefined
  const shownTier = adjusted ?? pickedTier
  // 改过物料的档位：档位卡片上的价格是原方案，标出来
  const adjustedTiers = tiers
    .filter((t) => Object.keys(changedQty(t, editsByTier[t.tier] ?? {})).length > 0)
    .map((t) => t.tier)
  const pick = (key: string) => setPicked(key)
  const preview = turn.interrupt
    ? shownTier && turn.interrupt.action === "generate_quote"
      ? {
          ...turn.interrupt.preview,
          tier: shownTier.tier,
          name: adjusted ? `${shownTier.name}（已调整）` : shownTier.name,
          summary: shownTier.summary,
          total_price: shownTier.total_price,
          margin_rate: shownTier.margin_rate,
        }
      : turn.interrupt.preview
    : {}
  const decide = (decision: ResumeDecision) => {
    draft.clear()
    if (decision !== "approve") return onDecide(decision)
    const tier = pickedTier && !pickedTier.recommended ? pickedTier.tier : undefined
    onDecide(decision, tier, adjusted ? changes : undefined)
  }
  const [animate] = useState(live)
  const smooth = useSmoothText(turn.text, animate)
  const followUps = onAsk ? splitFollowUps(smooth) : null
  const text = followUps ? followUps.body : smooth
  const afterText = useSmoothText(turn.afterText, animate || turn.afterText === "")
  const typing = smooth.length < turn.text.length || afterText.length < turn.afterText.length
  const seconds = Math.max(1, Math.round(((turn.endedAt ?? Date.now()) - turn.startedAt) / 1000))
  const showCaret = (live || typing) && (turn.text.length > 0 || turn.steps.length > 0)
  // 确认后的续写在卡片下面；光标跟着正在输出的那一段
  const caretAfter = showCaret && turn.afterText.length > 0
  // 生成中：卡片等前面的说明打完、后端停下（等确认或已结束）再出现
  const showCards = !(live || typing) || (Boolean(turn.interrupt) && smooth.length >= turn.text.length)
  return (
    <div className="flex gap-3">
      <span
        className={cn(
          // 手机上不占一列，方案卡和物料清单用满宽度
          "text-ai inline-flex shrink-0 items-center justify-center rounded-full border border-zinc-200 bg-white max-sm:hidden",
          compact ? "size-6" : "size-7",
        )}
      >
        <Sparkles className="size-3.5" />
      </span>
      <div className={cn("min-w-0 flex-1 space-y-3.5", compact ? "text-sm leading-6" : "text-chat")}>
        {turn.steps.length > 0 || (live && !turn.text) ? (
          <ThinkBlock
            steps={turn.steps}
            live={live && !turn.text}
            seconds={seconds}
            onRetry={readonly ? undefined : onRetry}
          />
        ) : null}
        {text ? (
          <div className={cn("prose-chat break-words", showCaret && !caretAfter && "[&>*:last-child]:caret")}>
            <ChatMarkdown text={text} />
          </div>
        ) : null}
        {showCards
          ? turn.artifacts
              .filter((a) => a.type !== "action_result")
              .map((a) => (
                <div
                  key={a.id}
                  // 三档方案卡：出来时滚到卡片顶部（下面还有确认卡，一直跟到底会把方案顶出视口）
                  data-scroll-anchor={!readonly && a.type === "solution_tiers" ? "" : undefined}
                  className={cn(animate && "animate-in fade-in slide-in-from-bottom-1 duration-300")}
                >
                  {a.type === "bom" && canEdit && baseTier && isCoreTier(a.data) ? (
                    <BomEditor tier={baseTier} edits={edits} onChange={setEdits} />
                  ) : (
                    <ArtifactView
                      artifact={a.type === "bom" && shownTier ? { ...a, data: shownTier } : a}
                      onConfirmRequirement={onConfirmRequirement}
                      readonly={readonly || busy}
                      selectedTier={pickedTier?.tier}
                      onSelectTier={canPick ? pick : undefined}
                      adjustedTiers={canEdit ? adjustedTiers : undefined}
                    />
                  )}
                </div>
              ))
          : null}
        {showCards && pending && draft.notice ? <DraftNoticeLine notice={draft.notice} /> : null}
        {showCards && turn.interrupt ? (
          <ConfirmCard
            title={turn.interrupt.title}
            rows={previewRows(preview)}
            decision={turn.interrupt.decision}
            result={actionResult}
            busy={busy || readonly}
            onDecide={decide}
          />
        ) : showCards && actionResult ? (
          // 历史记录里没有确认卡片：只显示执行结果
          <ResultLine result={actionResult} />
        ) : null}
        {afterText ? (
          <div className={cn("prose-chat break-words", caretAfter && "[&>*:last-child]:caret")}>
            <ChatMarkdown text={afterText} />
          </div>
        ) : null}
        {turn.status === "error" && turn.error ? (
          <ErrorBanner error={turn.error} onRetry={onRetry} disabled={busy || readonly} />
        ) : null}
        {turn.status === "stopped" ? <div className="text-xs text-zinc-400">已停止生成</div> : null}
        {followUps?.questions.length && turn.status === "done" && !typing && !readonly ? (
          <div className="flex flex-col items-start gap-1.5" aria-label="可以接着问">
            {followUps.questions.map((q) => (
              <button
                key={q}
                type="button"
                disabled={busy}
                onClick={() => onAsk?.(q)}
                className="inline-flex max-w-full items-start gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-left text-sm text-zinc-600 hover:border-zinc-300 hover:bg-zinc-50 disabled:opacity-50"
              >
                <CornerDownRight className="mt-0.5 size-3.5 shrink-0 text-zinc-400" />
                {q}
              </button>
            ))}
          </div>
        ) : null}
        {prdOpportunity && showCards && tiers.some((t) => Array.isArray(t.specs?.modules)) ? (
          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
            <Button variant="outline" size="xs" onClick={() => setPrdOpen(true)}>
              <FileText />
              PRD 规格书
            </Button>
            按需求清单生成需求规格说明书，可复制到飞书 / 钉钉 / Notion
            <PrdDialog
              oppId={prdOpportunity.id}
              title={prdOpportunity.name}
              canGenerate={prdOpportunity.canGenerate}
              open={prdOpen}
              onOpenChange={setPrdOpen}
            />
          </div>
        ) : null}
        {turn.status === "done" && !typing ? (
          <MsgActions
            text={[turn.text, turn.afterText].filter(Boolean).join("\n\n")}
            onRegenerate={readonly || busy ? undefined : onRetry}
            feedback={feedback}
          />
        ) : null}
      </div>
    </div>
  )
}

/** 恢复了离开前的调整，或者方案已更新没法恢复：提示确认前再核对 */
function DraftNoticeLine({ notice }: { notice: "restored" | "stale" }) {
  return (
    <p role="status" className="flex items-center gap-1.5 text-xs text-amber-700">
      <CircleAlert className="size-3.5 shrink-0" />
      {notice === "restored"
        ? "已恢复你离开前选的档位和物料调整，确认前请再核对一遍"
        : "方案已经重新生成，离开前的档位和物料调整没有恢复，请重新核对后再确认"}
    </p>
  )
}

/** 本条回复里最新一份三档方案（core 结构）；没有返回空数组 */
function coreTiers(artifacts: AgentArtifact[]): CoreSolutionTier[] {
  const a = [...artifacts].reverse().find((x) => x.type === "solution_tiers")
  return a && isCoreTiers(a.data) ? a.data : []
}
