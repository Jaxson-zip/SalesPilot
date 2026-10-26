"use client"

import { Download, X } from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { selectionLabel } from "@/lib/selection"

/**
 * 批量操作栏：勾选了行之后替换 ViewBar 显示（高度与 ViewBar 一致，切换时不跳动）。
 * 「已选 N 条」·「导出所选」· 页面自己的批量动作（extra）·「取消选择」
 */
export function BulkBar({
  count,
  onExport,
  onClear,
  extra,
}: {
  count: number
  onExport: () => void
  onClear: () => void
  extra?: ReactNode
}) {
  return (
    <div
      role="toolbar"
      aria-label="批量操作"
      className="flex h-10 shrink-0 items-center gap-1.5 border-b border-zinc-200 bg-zinc-50 px-3"
    >
      <span className="mr-1 font-medium tabular-nums">{selectionLabel(count)}</span>
      <Button variant="outline" size="xs" className="h-7" onClick={onExport}>
        <Download />
        导出所选
      </Button>
      {extra}
      <div className="flex-1" />
      <Button variant="ghost" size="xs" className="h-7 text-zinc-600" onClick={onClear}>
        <X />
        取消选择
      </Button>
    </div>
  )
}
