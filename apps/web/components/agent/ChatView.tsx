"use client"

import { Download, Ellipsis, History, Pencil, Trash2 } from "lucide-react"
import { useEffect, useRef, type ReactNode } from "react"

import { AiMessage } from "@/components/agent/AiMessage"
import { UserMsg } from "@/components/agent/UserMsg"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { ChatTurn } from "@/lib/agent-reducer"
import type { ResumeDecision } from "@/types/api"

/** 会话标题栏：历史按钮（<768）+ 标题 + 更多菜单 */
function ChatHeader({
  title,
  onToggleHistory,
  onDelete,
}: {
  title: string
  onToggleHistory: () => void
  onDelete: () => void
}) {
  return (
    <div className="flex h-11 shrink-0 items-center gap-2 border-b border-zinc-100 px-3 sm:px-4">
      <button
        type="button"
        title="会话历史"
        onClick={onToggleHistory}
        className="inline-flex size-7 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100 md:hidden"
      >
        <History className="size-4" />
      </button>
      <span className="min-w-0 flex-1 truncate font-medium">{title}</span>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            title="更多"
            className="inline-flex size-7 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100"
          >
            <Ellipsis className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-[180px]">
          <DropdownMenuItem disabled>
            <Pencil />
            重命名
          </DropdownMenuItem>
          <DropdownMenuItem disabled>
            <Download />
            导出对话
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={onDelete}>
            <Trash2 />
            删除
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

/** 会话区：顶部标题栏 + 居中消息列表（最大宽 760）+ 底部输入框 */
export function ChatView({
  title,
  turns,
  busy,
  composer,
  onToggleHistory,
  onDecide,
  onRetry,
  onDelete,
}: {
  title: string
  turns: ChatTurn[]
  busy: boolean
  composer: ReactNode
  onToggleHistory: () => void
  onDecide: (decision: ResumeDecision) => void
  onRetry: () => void
  onDelete: () => void
}) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // 新内容到达时滚动到底部
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [turns])

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <ChatHeader title={title} onToggleHistory={onToggleHistory} onDelete={onDelete} />
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
