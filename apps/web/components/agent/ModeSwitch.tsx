"use client"

import { GraduationCap, Loader2, Sparkles } from "lucide-react"

import { MODE_LABEL, type AgentMode } from "@/lib/agent-mode"
import { cn } from "@/lib/utils"

const MODES: { mode: AgentMode; icon: typeof Sparkles; hint: string }[] = [
  { mode: "work", icon: Sparkles, hint: "出方案报价、记跟进、推进商机、报销审批" },
  { mode: "learn", icon: GraduationCap, hint: "新人了解公司产品、报价方式、制度和竞品，只问不改数据" },
]

/**
 * 做方案 / 学习问答 切换（分段按钮）。两种模式各有自己的当前对话，切过去显示那边上次的对话；
 * 另一边还在生成时按钮上转圈。compact：对话标题栏里的小尺寸，手机上只显示图标
 */
export function ModeSwitch({
  mode,
  onChange,
  disabled,
  compact,
  streaming,
}: {
  mode: AgentMode
  onChange: (mode: AgentMode) => void
  disabled?: boolean
  compact?: boolean
  streaming?: Partial<Record<AgentMode, boolean>>
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
            aria-label={MODE_LABEL[m.mode]}
            disabled={disabled}
            onClick={() => onChange(m.mode)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md transition-colors disabled:opacity-50",
              compact ? "h-6 px-2 text-xs" : "h-7 px-3 text-sm",
              active ? "bg-white font-medium text-zinc-900 shadow-xs" : "text-zinc-500 hover:text-zinc-800",
            )}
          >
            {streaming?.[m.mode] && !active ? (
              <Loader2 className="size-3.5 animate-spin" aria-label="正在生成" />
            ) : (
              <m.icon className="size-3.5" />
            )}
            <span className={compact ? "hidden sm:inline" : undefined}>{MODE_LABEL[m.mode]}</span>
          </button>
        )
      })}
    </div>
  )
}
