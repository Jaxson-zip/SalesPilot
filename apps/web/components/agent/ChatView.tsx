"use client"

import { SquarePen } from "lucide-react"
import { useEffect, useRef, type ReactNode } from "react"

import { AiMessage } from "@/components/agent/AiMessage"
import type { MsgFeedback } from "@/components/agent/MsgActions"
import { ModeSwitch } from "@/components/agent/ModeSwitch"
import { UserMsg } from "@/components/agent/UserMsg"
import { useSession } from "@/components/shell/SessionProvider"
import { useMyRatings, useRate } from "@/hooks/useAiFeedback"
import type { AgentMode } from "@/lib/agent-mode"
import { feedbackSlots } from "@/lib/agent-feedback"
import type { AssistantTurn, ChatTurn } from "@/lib/agent-reducer"
import type { QtyEdits } from "@/lib/bom-adjust"
import { nextStick } from "@/lib/chat-scroll"
import { quoteDraftKey } from "@/lib/quote-draft"
import { cn } from "@/lib/utils"
import type { ResumeDecision } from "@/types/api"

const ICON_BTN = "inline-flex size-7 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100"

/**
 * 会话标题栏：模式切换 + 标题 + 新对话（会话记录在页面标题行的「历史记录」面板里）。
 * 模式随会话固定：对话中切换会另起一个该模式的新对话，当前对话留在历史记录里
 */
function ChatHeader({
  title,
  onNew,
  mode,
  onModeChange,
  streamingModes,
}: {
  title: string
  onNew: () => void
  mode: AgentMode
  onModeChange?: (mode: AgentMode) => void
  /** 两种模式各自是否在生成：另一边在后台生成时切换按钮上转圈 */
  streamingModes?: Partial<Record<AgentMode, boolean>>
}) {
  return (
    <div className="flex h-11 shrink-0 items-center gap-2 border-b border-zinc-100 px-3 sm:px-4">
      {onModeChange ? <ModeSwitch mode={mode} onChange={onModeChange} streaming={streamingModes} compact /> : null}
      <span className="min-w-0 flex-1 truncate font-medium" title={title}>
        {title}
      </span>
      <button type="button" title="新对话" aria-label="新对话" onClick={onNew} className={ICON_BTN}>
        <SquarePen className="size-4" />
      </button>
    </div>
  )
}

/** 会话区：顶部标题栏 + 居中消息列表（最大宽 760）+ 底部输入框 */
export function ChatView({
  title,
  turns,
  busy,
  loading,
  composer,
  onDecide,
  onRetry,
  onNew,
  onConfirmRequirement,
  mode = "work",
  onModeChange,
  streamingModes,
  onAsk,
  prdOpportunity,
  threadId = null,
}: {
  title: string
  turns: ChatTurn[]
  busy: boolean
  /** 正在切换到另一个会话 */
  loading?: boolean
  composer: ReactNode
  onDecide: (decision: ResumeDecision, tier?: string, items?: QtyEdits) => void
  onRetry: () => void
  onNew: () => void
  onConfirmRequirement?: (requirement: Record<string, unknown>) => void
  mode?: AgentMode
  /** 切换模式（另起新对话）；管理员只能查询，不显示 */
  onModeChange?: (mode: AgentMode) => void
  /** 两种模式各自是否在生成：另一边在后台生成时切换按钮上转圈 */
  streamingModes?: Partial<Record<AgentMode, boolean>>
  /** 学习问答：点回答末尾的追问建议直接发送 */
  onAsk?: (question: string) => void
  prdOpportunity?: { id: string; name: string; canGenerate: boolean }
  /** 当前会话 id：点赞 / 点踩按「会话 + 第几条 AI 回复」存 */
  threadId?: string | null
}) {
  const learn = mode === "learn"
  const { userId } = useSession()
  const draftKey = userId && threadId ? quoteDraftKey(userId, threadId) : null
  const ratings = useMyRatings(threadId).data
  const rate = useRate(threadId, mode)
  const slots = feedbackSlots(turns)
  const feedbackFor = (t: AssistantTurn): MsgFeedback | undefined => {
    const m = slots.get(t.id)
    if (!threadId || !m) return undefined
    return {
      rating: ratings?.[m.index]?.rating ?? null,
      onRate: (rating, comment) =>
        rate.mutate({
          message_index: m.index,
          rating,
          comment: comment ?? null,
          question: m.question,
          answer: [t.text, t.afterText].filter(Boolean).join("\n\n"),
        }),
    }
  }
  const scrollRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  // 停在底部附近时跟随新内容（正文是逐字显示的，内容高度一直在变）；用户往上翻看时不打扰
  const stick = useRef(true)

  useEffect(() => {
    stick.current = true
  }, [turns.length])

  useEffect(() => {
    const el = scrollRef.current
    const content = contentRef.current
    if (!el || !content) return
    let lastTop = el.scrollTop
    const onScroll = () => {
      const { scrollTop: top, scrollHeight, clientHeight } = el
      stick.current = nextStick(stick.current, { lastTop, top, scrollHeight, clientHeight })
      lastTop = top
    }
    const follow = () => {
      if (!stick.current) return
      // 新出现的锚点（三档方案卡）：滚到它的顶部并停止跟随，后面的说明和确认卡往下翻看
      const anchor = content.querySelector<HTMLElement>("[data-scroll-anchor]:not([data-anchored])")
      if (anchor) {
        anchor.dataset.anchored = ""
        const offset = anchor.getBoundingClientRect().top - el.getBoundingClientRect().top
        if (offset > 0 && anchor.offsetHeight > 0) {
          el.scrollTop += offset - 16
          stick.current = false
          return
        }
      }
      el.scrollTop = el.scrollHeight
    }
    follow()
    el.addEventListener("scroll", onScroll, { passive: true })
    const ro = new ResizeObserver(follow)
    ro.observe(content)
    return () => {
      el.removeEventListener("scroll", onScroll)
      ro.disconnect()
    }
  }, [])

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <ChatHeader title={title} onNew={onNew} mode={mode} onModeChange={onModeChange} streamingModes={streamingModes} />
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
        <div
          ref={contentRef}
          aria-busy={loading || undefined}
          className={cn(
            "mx-auto max-w-[760px] space-y-7 px-4 py-6 transition-opacity sm:px-6",
            loading && "opacity-50",
          )}
        >
          {turns.map((t, i) =>
            t.role === "user" ? (
              <UserMsg key={t.id} text={t.text} material={t.material} />
            ) : (
              <AiMessage
                key={t.id}
                turn={t}
                busy={busy}
                onDecide={onDecide}
                onRetry={onRetry}
                onConfirmRequirement={onConfirmRequirement}
                onAsk={learn ? onAsk : undefined}
                prdOpportunity={learn ? undefined : prdOpportunity}
                readonly={i !== turns.length - 1}
                feedback={feedbackFor(t)}
                draftKey={i === turns.length - 1 ? draftKey : null}
              />
            ),
          )}
        </div>
      </div>
      <div className="shrink-0 px-3 pb-3 sm:px-6 sm:pb-4">
        <div className="mx-auto max-w-[760px]">
          {composer}
          <p className="mt-2 text-center text-[11px] text-zinc-400">
            {learn
              ? "内容由 AI 根据知识库和系统配置整理，以公司正式制度为准"
              : "内容由 AI 生成，价格与毛利以报价引擎计算为准"}
          </p>
        </div>
      </div>
    </div>
  )
}
