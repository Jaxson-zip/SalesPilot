"use client"

import { X } from "lucide-react"
import type { ReactNode } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { Button } from "@/components/ui/button"
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"
import { DISCARD_FORM_CONFIRM } from "@/lib/confirm-texts"
import { cn } from "@/lib/utils"

/**
 * 右侧 Sheet（与原型一致）：四周留 8px、圆角浮层，≥640 宽 440px，<640 占满屏幕（仍留 8px）。
 * 结构：标题行 48px（标题 + 关闭）+ 可滚动内容 + 底部按钮。新建表单与记录预览共用。
 * dirty：表单有没保存的内容时，按 Esc、点遮罩、点 ✕ 先确认再关闭（底部「取消」是明确放弃，不再问）。
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
  wide,
  dirty,
  children,
}: {
  dirty?: boolean
  /** 内容是表格时加宽到 640px */
  wide?: boolean
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  footer?: ReactNode
  children: ReactNode
}) {
  const { ask, dialog } = useConfirmAction()
  const change = (next: boolean) => {
    if (next || !dirty) return onOpenChange(next)
    ask({ ...DISCARD_FORM_CONFIRM, onConfirm: () => onOpenChange(false) })
  }
  return (
    <Sheet open={open} onOpenChange={change}>
      <SheetContent
        side="right"
        showCloseButton={false}
        className={cn(PANEL_CLASS, wide && "data-[side=right]:sm:w-[640px] data-[side=right]:sm:max-w-[640px]")}
      >
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
      {dialog}
    </Sheet>
  )
}
