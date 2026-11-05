"use client"

import { Check } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export interface ChipOption {
  value: string
  label: string
  /** 次要说明（职位等） */
  hint?: string | null
}

/**
 * Chip 多选：每个选项是一个可切换的 chip（aria-pressed），选中为深色。
 * fixed：不可移除的 chip（例如申请人本人），始终显示为选中。
 */
export function ChipMultiSelect({
  ariaLabel,
  options,
  value,
  onToggle,
  fixed,
  empty,
  invalid,
}: {
  ariaLabel: string
  options: ChipOption[]
  value: string[]
  onToggle: (id: string) => void
  fixed?: ReactNode
  empty?: ReactNode
  invalid?: boolean
}) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn(
        "flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border px-2 py-1.5",
        invalid ? "border-destructive" : "border-zinc-200",
      )}
    >
      {fixed}
      {options.map((o) => {
        const on = value.includes(o.value)
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            onClick={() => onToggle(o.value)}
            className={cn(
              "inline-flex h-6 max-w-full items-center gap-1 rounded-full border px-2 text-xs outline-none focus-visible:ring-1 focus-visible:ring-zinc-400",
              on
                ? "border-zinc-900 bg-zinc-900 text-white hover:bg-zinc-800"
                : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50",
            )}
          >
            {on ? <Check className="size-3 shrink-0" /> : null}
            <span className="truncate">{o.label}</span>
            {o.hint ? <span className={cn("truncate", on ? "text-white/70" : "text-zinc-500")}>{o.hint}</span> : null}
          </button>
        )
      })}
      {options.length === 0 && !fixed ? <span className="text-zinc-500">{empty}</span> : null}
      {options.length === 0 && fixed && empty ? <span className="text-xs text-zinc-500">{empty}</span> : null}
    </div>
  )
}

/** 不可移除的 chip（申请人本人） */
export function FixedChip({ label }: { label: string }) {
  return (
    <span
      className="inline-flex h-6 items-center gap-1 rounded-full border border-zinc-300 bg-zinc-100 px-2 text-xs text-zinc-700"
      title="申请人本人，始终计入人数"
    >
      {label}
    </span>
  )
}
