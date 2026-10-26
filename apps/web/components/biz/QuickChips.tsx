"use client"

import { cn } from "@/lib/utils"

export interface QuickChip {
  key: string
  label: string
  /** 鼠标悬停时的说明（例如模板示例） */
  title?: string
}

/**
 * 一排可点的快捷选项（模板、常用原因、常用任务）：点一下把内容填进表单，填完仍可修改。
 * 用 role="group" + aria-label 命名，测试和读屏都能定位。
 */
export function QuickChips({
  label,
  items,
  onPick,
  active,
  className,
}: {
  label: string
  items: QuickChip[]
  onPick: (key: string) => void
  /** 当前选中的 key（模板），不传则都不高亮 */
  active?: string | null
  className?: string
}) {
  if (items.length === 0) return null
  return (
    <div role="group" aria-label={label} className={cn("flex flex-wrap gap-1.5", className)}>
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          title={item.title}
          aria-pressed={active === undefined ? undefined : active === item.key}
          onClick={() => onPick(item.key)}
          className={cn(
            "inline-flex h-7 items-center rounded-full border px-2.5 text-xs transition-colors",
            active === item.key
              ? "border-zinc-900 bg-zinc-900 text-white"
              : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50",
          )}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
