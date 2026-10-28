"use client"

import { SquarePen } from "lucide-react"
import { useEffect, useRef, type ReactNode } from "react"

import { AiMessage } from "@/components/agent/AiMessage"
import { UserMsg } from "@/components/agent/UserMsg"
import type { ChatTurn } from "@/lib/agent-reducer"
import type { ResumeDecision } from "@/types/api"

const ICON_BTN = "inline-flex size-7 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100"

/** 会话标题栏：标题 + 新对话（会话记录开关在页面标题行） */
function ChatHeader({ title, onNew }: { title: string; onNew: () => void }) {
  return (
    <div className="flex h-11 shrink-0 items-center gap-2 border-b border-zinc-100 px-3 sm:px-4">
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
  composer,
  onDecide,
  onRetry,
  onNew,
}: {
  title: string
  turns: ChatTurn[]
  busy: boolean
  composer: ReactNode
  onDecide: (decision: ResumeDecision) => void
  onRetry: () => void
  onNew: () => void
}) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // 新内容到达时滚动到底部
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [turns])

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <ChatHeader title={title} onNew={onNew} />
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
        <div className="mx-auto max-w-[760px] space-y-7 px-4 py-6 sm:px-6">
          {turns.map((t, i) =>
            t.role === "user" ? (
              <UserMsg key={t.id} text={t.text} />
            ) : (
              <AiMessage
                key={t.id}
                turn={t}
                busy={busy}
                onDecide={onDecide}
                onRetry={onRetry}
                readonly={i !== turns.length - 1}
              />
            ),
          )}
        </div>
      </div>
      <div className="shrink-0 px-3 pb-3 sm:px-6 sm:pb-4">
        <div className="mx-auto max-w-[760px]">
          {composer}
          <p className="mt-2 text-center text-[11px] text-zinc-400">内容由 AI 生成，价格与毛利以报价引擎计算为准</p>
        </div>
      </div>
    </div>
  )
}
