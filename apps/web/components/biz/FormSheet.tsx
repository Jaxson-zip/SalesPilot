"use client"

import { X } from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"

/**
 * 右侧 Sheet（与原型一致）：四周留 8px、圆角浮层，≥640 宽 440px，<640 占满屏幕（仍留 8px）。
 * 结构：标题行 48px（标题 + 关闭）+ 可滚动内容 + 底部按钮。新建表单与记录预览共用。
 */
const PANEL_CLASS = [
  "gap-0 overflow-hidden rounded-lg border border-zinc-200 p-0 shadow-xl",
  "data-[side=right]:inset-y-2 data-[side=right]:right-2 data-[side=right]:left-2 data-[side=right]:h-auto data-[side=right]:w-auto",
  "data-[side=right]:sm:left-auto data-[side=right]:sm:w-[440px] data-[side=right]:sm:max-w-[440px]",
].join(" ")

export function FormSheet({
  open,
  onOpenChange,
  title,
  description,
  footer,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  footer?: ReactNode
  children: ReactNode
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" showCloseButton={false} className={PANEL_CLASS}>
        <div className="flex h-12 shrink-0 items-center gap-2 border-b border-zinc-100 pr-3 pl-5">
          <SheetTitle className="min-w-0 flex-1 truncate text-sm font-semibold">{title}</SheetTitle>
          <SheetClose asChild>
            <Button variant="ghost" size="icon-sm" aria-label="关闭" className="shrink-0 text-zinc-500">
              <X />
            </Button>
          </SheetClose>
        </div>
        <SheetDescription className="sr-only">{description ?? title}</SheetDescription>
        <div className="min-h-0 flex-1 space-y-4 overflow-x-hidden overflow-y-auto p-5">{children}</div>
        {footer ? (
          <div className="flex shrink-0 flex-wrap justify-end gap-2 border-t border-zinc-100 px-5 py-3">{footer}</div>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
