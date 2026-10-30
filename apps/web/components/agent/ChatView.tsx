"use client"

import { SquarePen } from "lucide-react"
import { useEffect, useRef, type ReactNode } from "react"

import { AiMessage } from "@/components/agent/AiMessage"
import { ModeSwitch } from "@/components/agent/ModeSwitch"
import { UserMsg } from "@/components/agent/UserMsg"
import type { AgentMode } from "@/lib/agent-mode"
import type { ChatTurn } from "@/lib/agent-reducer"
import type { QtyEdits } from "@/lib/bom-adjust"
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
  busy,
}: {
  title: string
  onNew: () => void
  mode: AgentMode
  onModeChange?: (mode: AgentMode) => void
  busy?: boolean
}) {
  return (
    <div className="flex h-11 shrink-0 items-center gap-2 border-b border-zinc-100 px-3 sm:px-4">
      {onModeChange ? <ModeSwitch mode={mode} onChange={onModeChange} disabled={busy} compact /> : null}
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
  onAsk,
  prdOpportunity,
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
  /** 学习问答：点回答末尾的追问建议直接发送 */
  onAsk?: (question: string) => void
  prdOpportunity?: { id: string; name: string; canGenerate: boolean }
}) {
  const learn = mode === "learn"
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
    const onScroll = () => {
      stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
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
      <ChatHeader title={title} onNew={onNew} mode={mode} onModeChange={onModeChange} busy={busy} />
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
