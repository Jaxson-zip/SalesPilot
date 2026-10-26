"use client"

import type { ReactNode } from "react"

import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"

/**
 * 右侧 Sheet（440px，<640 占满屏幕）：标题行 48px + 可滚动内容 + 底部按钮。
 * 新建表单与记录预览共用。
 */
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
      <SheetContent side="right" className="gap-0 p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-[440px]">
        <div className="flex h-12 shrink-0 items-center border-b border-zinc-100 px-5 pr-12">
          <SheetTitle className="truncate text-sm font-semibold">{title}</SheetTitle>
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
