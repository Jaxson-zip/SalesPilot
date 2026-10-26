"use client"

import { Download } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { bomToCsv, safeFileName } from "@/lib/artifacts"
import { downloadText } from "@/lib/download"
import { formatFen } from "@/lib/format"
import type { BomData } from "@/types/api"

/** 默认导出：CSV（UTF-8 BOM，金额按元） */
function exportBom(bom: BomData): void {
  downloadText(bomToCsv(bom), `${safeFileName(bom.title)}.csv`)
  toast.success("物料清单已导出")
}

/** 物料清单：≥640 表格；<640 逐行列表（不横向滚动）；「导出」默认导出 CSV */
export function BomTable({ bom, onExport }: { bom: BomData; onExport?: () => void }) {
  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 text-sm">
      <div className="flex h-10 items-center justify-between border-b border-zinc-200 bg-zinc-50 px-3.5">
        <span className="truncate font-medium">{bom.title}</span>
        <Button
          variant="ghost"
          size="xs"
          className="h-7"
          aria-label="导出物料清单"
          onClick={onExport ?? (() => exportBom(bom))}
        >
          <Download />
          导出
        </Button>
      </div>
      <table className="hidden w-full table-fixed sm:table">
        <thead>
          <tr className="h-8 text-zinc-500">
            <th className="px-3.5 text-left font-normal">项目</th>
            <th className="w-24 px-2 text-left font-normal">数量</th>
            <th className="w-28 px-2 text-right font-normal">成本</th>
            <th className="w-28 px-3.5 text-right font-normal">售价</th>
          </tr>
        </thead>
        <tbody>
          {bom.items.map((r) => (
            <tr key={r.name} className="h-9 border-t border-zinc-100">
              <td className="truncate px-3.5">{r.name}</td>
              <td className="truncate px-2 text-zinc-500">{r.quantity}</td>
              <td className="px-2 text-right text-zinc-500 tabular-nums">{formatFen(r.cost)}</td>
              <td className="px-3.5 text-right tabular-nums">{formatFen(r.price)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="divide-y divide-zinc-100 sm:hidden">
        {bom.items.map((r) => (
          <div key={r.name} className="flex items-start justify-between gap-3 px-3.5 py-2.5">
            <div className="min-w-0">
              <div className="break-words">{r.name}</div>
              <div className="mt-0.5 text-xs text-zinc-500">
                {r.quantity} · 成本 {formatFen(r.cost)}
              </div>
            </div>
            <div className="shrink-0 font-medium tabular-nums">{formatFen(r.price)}</div>
          </div>
        ))}
      </div>
      {bom.totals.length > 0 ? (
        <div className="grid grid-cols-2 border-t border-zinc-200 sm:grid-cols-4">
          {bom.totals.map((t) => (
            <div key={t.label} className="min-w-0 px-3.5 py-2.5">
              <div className="text-xs text-zinc-500">{t.label}</div>
              <div className="truncate font-semibold tabular-nums">{t.value}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
