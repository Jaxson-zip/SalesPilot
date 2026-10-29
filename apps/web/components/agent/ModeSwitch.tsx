"use client"

import { GraduationCap, Sparkles } from "lucide-react"

import { MODE_LABEL, type AgentMode } from "@/lib/agent-mode"
import { cn } from "@/lib/utils"

const MODES: { mode: AgentMode; icon: typeof Sparkles; hint: string }[] = [
  { mode: "work", icon: Sparkles, hint: "出方案报价、记跟进、推进商机、报销审批" },
  { mode: "learn", icon: GraduationCap, hint: "新人了解公司产品、报价方式、制度和竞品，只问不改数据" },
]

/** 做方案 / 学习问答 切换（分段按钮）；会话开始后切换会另起新对话 */
export function ModeSwitch({
  mode,
  onChange,
  disabled,
}: {
  mode: AgentMode
  onChange: (mode: AgentMode) => void
  disabled?: boolean
}) {
  return (
    <div
      role="radiogroup"
      aria-label="对话模式"
      className="inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5"
    >
      {MODES.map((m) => {
        const active = m.mode === mode
        return (
          <button
            key={m.mode}
            type="button"
            role="radio"
            aria-checked={active}
            title={m.hint}
            disabled={disabled}
            onClick={() => onChange(m.mode)}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-md px-3 text-sm transition-colors disabled:opacity-50",
              active ? "bg-white font-medium text-zinc-900 shadow-xs" : "text-zinc-500 hover:text-zinc-800",
            )}
          >
            <m.icon className="size-3.5" />
            {MODE_LABEL[m.mode]}
          </button>
        )
      })}
    </div>
  )
}
