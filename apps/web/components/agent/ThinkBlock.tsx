"use client"

import { ChevronDown, ListChecks } from "lucide-react"
import { useState } from "react"

import { ToolStep } from "@/components/agent/ToolStep"
import type { AgentStep } from "@/lib/agent-reducer"
import { cn } from "@/lib/utils"

/**
 * ThinkBlock / ThoughtChain：执行过程折叠块（DeepSeek「已深度思考」样式）。
 * 流式时标题为「正在调用工具…」并默认展开；结束后显示「已完成 N 步（用时 X 秒）」。
 */
export function ThinkBlock({
  steps,
  live,
  seconds,
  onRetry,
}: {
  steps: AgentStep[]
  live: boolean
  seconds: number
  onRetry?: () => void
}) {
  const [userOpen, setUserOpen] = useState<boolean | null>(null)
  const open = userOpen ?? live
  const title = live ? "正在调用工具…" : `已完成 ${steps.length} 步（用时 ${seconds} 秒）`
  return (
    <div>
      <button
        type="button"
        onClick={() => setUserOpen(!open)}
        className="inline-flex h-7 items-center gap-1.5 rounded-lg bg-zinc-100 px-2.5 text-xs text-zinc-600 hover:bg-zinc-200"
      >
        {live ? (
          <span className="inline-block size-3 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
        ) : (
          <ListChecks className="size-3.5" />
        )}
        <span>{title}</span>
        <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && steps.length > 0 ? (
        <div className="mt-3 ml-1 border-l-2 border-zinc-200 pl-4">
          {steps.map((s) => (
            <ToolStep key={s.id} step={s} onRetry={onRetry} />
          ))}
        </div>
      ) : null}
    </div>
  )
}
