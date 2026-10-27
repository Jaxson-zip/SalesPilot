"use client"

import { Info, type LucideIcon } from "lucide-react"
import { useEffect, useRef, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

const OPEN_DELAY = 150
const CLOSE_DELAY = 200

/**
 * 说明类内容的悬浮卡片（替代「只放几行字的整屏侧栏」）：
 * 鼠标移入稍等即展开，移到卡片里继续停留不会收起；点击可固定 / 收起（触屏设备只能点击）；Esc 关闭。
 */
export function InfoPopover({
  label,
  icon: Icon = Info,
  variant = "button",
  title,
  children,
  align = "end",
  className,
}: {
  label: string
  icon?: LucideIcon
  /** button：页头按钮；link：行内文字链接；icon：只显示图标 */
  variant?: "button" | "link" | "icon"
  title?: string
  children: ReactNode
  align?: "start" | "center" | "end"
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const later = (next: boolean, ms: number) => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setOpen(next), ms)
  }
  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), [])

  const hover = {
    onPointerEnter: (e: React.PointerEvent) => e.pointerType === "mouse" && later(true, OPEN_DELAY),
    onPointerLeave: (e: React.PointerEvent) => e.pointerType === "mouse" && later(false, CLOSE_DELAY),
  }
  const trigger =
    variant === "link" ? (
      <button
        type="button"
        className="inline-flex items-center gap-1 text-xs text-zinc-500 underline-offset-2 hover:text-zinc-800 hover:underline"
      >
        <Icon className="size-3.5" />
        {label}
      </button>
    ) : (
      <Button
        variant={variant === "icon" ? "ghost" : "outline"}
        size={variant === "icon" ? "icon-xs" : "sm"}
        aria-label={variant === "icon" ? label : undefined}
        title={variant === "icon" ? label : undefined}
      >
        <Icon />
        {variant === "icon" ? null : <span className="max-sm:hidden">{label}</span>}
      </Button>
    )

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild {...hover}>
        {trigger}
      </PopoverTrigger>
      <PopoverContent
        align={align}
        className={cn("w-80 gap-3 p-0", className)}
        aria-label={title ?? label}
        {...hover}
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        {title ? <div className="border-b border-zinc-100 px-4 pt-3 pb-2.5 font-medium">{title}</div> : null}
        <div className={cn("px-4 pb-3.5", !title && "pt-3.5")}>{children}</div>
      </PopoverContent>
    </Popover>
  )
}
