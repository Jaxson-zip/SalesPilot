"use client"

import { CircleAlert, RotateCcw, Sparkles } from "lucide-react"
import { useState } from "react"

import { ArtifactView } from "@/components/agent/ArtifactView"
import { ChatMarkdown } from "@/components/agent/ChatMarkdown"
import { ConfirmCard } from "@/components/agent/ConfirmCard"
import { MsgActions } from "@/components/agent/MsgActions"
import { ThinkBlock } from "@/components/agent/ThinkBlock"
import { Button } from "@/components/ui/button"
import { useSmoothText } from "@/hooks/useSmoothText"
import type { AssistantTurn } from "@/lib/agent-reducer"
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
  readonly,
}: {
  turn: AssistantTurn
  compact?: boolean
  busy?: boolean
  /** 历史消息：不再响应确认 / 重试 */
  readonly?: boolean
  onDecide: (decision: ResumeDecision) => void
  onRetry: () => void
  onConfirmRequirement?: (requirement: Record<string, unknown>) => void
}) {
  const live = turn.status === "streaming"
  const [animate] = useState(live)
  const text = useSmoothText(turn.text, animate)
  const afterText = useSmoothText(turn.afterText, animate || turn.afterText === "")
  const typing = text.length < turn.text.length || afterText.length < turn.afterText.length
  const seconds = Math.max(1, Math.round(((turn.endedAt ?? Date.now()) - turn.startedAt) / 1000))
  const showCaret = (live || typing) && (turn.text.length > 0 || turn.steps.length > 0)
  // 确认后的续写在卡片下面；光标跟着正在输出的那一段
  const caretAfter = showCaret && turn.afterText.length > 0
  // 生成中：卡片等前面的说明打完、后端停下（等确认或已结束）再出现
  const showCards = !(live || typing) || (Boolean(turn.interrupt) && text.length >= turn.text.length)
  return (
    <div className="flex gap-3">
      <span
        className={cn(
          "text-ai inline-flex shrink-0 items-center justify-center rounded-full border border-zinc-200 bg-white",
          compact ? "size-6" : "size-7",
        )}
      >
        <Sparkles className="size-3.5" />
      </span>
      <div className={cn("min-w-0 flex-1 space-y-3.5", compact ? "text-sm leading-6" : "text-chat")}>
        {turn.steps.length > 0 || live ? (
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
          ? turn.artifacts.map((a) => (
              <div
                key={a.id}
                // 三档方案卡：出来时滚到卡片顶部（下面还有确认卡，一直跟到底会把方案顶出视口）
                data-scroll-anchor={!readonly && a.type === "solution_tiers" ? "" : undefined}
                className={cn(animate && "animate-in fade-in slide-in-from-bottom-1 duration-300")}
              >
                <ArtifactView artifact={a} onConfirmRequirement={onConfirmRequirement} readonly={readonly || busy} />
              </div>
            ))
          : null}
        {showCards && turn.interrupt ? (
          <ConfirmCard
            title={turn.interrupt.title}
            rows={previewRows(turn.interrupt.preview)}
            decision={turn.interrupt.decision}
            busy={busy || readonly}
            onDecide={onDecide}
          />
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
        {turn.status === "done" && !typing ? (
          <MsgActions
            text={[turn.text, turn.afterText].filter(Boolean).join("\n\n")}
            onRegenerate={readonly || busy ? undefined : onRetry}
          />
        ) : null}
      </div>
    </div>
  )
}
