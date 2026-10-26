import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

/** 记录详情左侧字段行：图标 + 标签（104px）+ 值；传 onClick 时才有可点击外观（hover 灰底） */
export function FieldRow({
  icon: Icon,
  label,
  children,
  onClick,
}: {
  icon: LucideIcon
  label: string
  children: ReactNode
  onClick?: () => void
}) {
  return (
    <div className="flex min-h-8 items-center">
      <span className="inline-flex w-[104px] shrink-0 items-center gap-1.5 text-zinc-500">
        <Icon className="size-3.5" />
        {label}
      </span>
      <div
        role={onClick ? "button" : undefined}
        tabIndex={onClick ? 0 : undefined}
        onClick={onClick}
        className={cn("min-w-0 flex-1 truncate rounded px-1.5 py-1", onClick && "cursor-pointer hover:bg-zinc-100")}
      >
        {children}
      </div>
    </div>
  )
}
