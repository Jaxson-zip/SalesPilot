"use client"

import { RotateCcw, Trash2, Undo2 } from "lucide-react"

import { ClientCosts } from "@/components/biz/ClientCosts"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { clientCostsOf, type CoreSolutionTier } from "@/lib/artifacts"
import { adjustTier, changedQty, parseQty, type QtyEdits } from "@/lib/bom-adjust"
import { formatFen, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"

/**
 * 待确认生成报价单时的物料清单：可以改数量、删掉某一项（客户说「监控不要了、调优加到 10 人天」），
 * 合计和毛利即时预览；不能加新物料（生成报价单后在报价单里加）。
 */
export function BomEditor({
  tier,
  edits,
  onChange,
}: {
  tier: CoreSolutionTier
  edits: QtyEdits
  onChange: (edits: QtyEdits) => void
}) {
  const preview = adjustTier(tier, edits)
  const changed = Object.keys(changedQty(tier, edits)).length
  const set = (sku: string, qty: number) => onChange({ ...edits, [sku]: qty })
  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 text-sm" aria-label="调整物料清单">
      <div className="flex h-10 items-center justify-between gap-2 border-b border-zinc-200 bg-zinc-50 px-3.5">
        <span className="truncate font-medium">
          {tier.name} · 物料清单
          <span className="ml-2 text-xs font-normal text-zinc-500">
            {changed ? `已调整 ${changed} 项` : "可改数量或删掉不要的项目"}
          </span>
        </span>
        {changed ? (
          <Button variant="ghost" size="xs" className="h-7" onClick={() => onChange({})}>
            <RotateCcw />
            恢复原方案
          </Button>
        ) : null}
      </div>
      <ul className="divide-y divide-zinc-100">
        {tier.items.map((i) => {
          const qty = edits[i.sku] ?? i.qty
          const removed = qty === 0
          return (
            <li key={i.sku} className="flex items-center gap-2 px-3.5 py-2">
              <span className={cn("min-w-0 flex-1 break-words", removed && "text-zinc-400 line-through")}>
                {i.name}
              </span>
              {removed ? (
                <Button variant="ghost" size="xs" className="h-7" onClick={() => set(i.sku, i.qty)}>
                  <Undo2 />
                  恢复
                </Button>
              ) : (
                <>
                  <span className="inline-flex shrink-0 items-center gap-1">
                    <Input
                      key={qty}
                      defaultValue={String(qty)}
                      inputMode="numeric"
                      aria-label={`${i.name}的数量`}
                      className="h-7 w-16 text-right tabular-nums"
                      onBlur={(e) => {
                        const n = parseQty(e.target.value)
                        if (n === undefined) e.target.value = String(qty)
                        else if (n !== qty) set(i.sku, n)
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") e.currentTarget.blur()
                      }}
                    />
                    <span className="w-6 text-xs text-zinc-500">{i.unit}</span>
                  </span>
                  <span className="hidden w-24 shrink-0 text-right tabular-nums sm:inline">
                    {formatFen(i.unit_price * qty)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label={`删除${i.name}`}
                    title="不要这一项"
                    disabled={preview.items.length === 1}
                    onClick={() => set(i.sku, 0)}
                  >
                    <Trash2 />
                  </Button>
                </>
              )}
            </li>
          )
        })}
      </ul>
      <div className="grid grid-cols-3 border-t border-zinc-200">
        <div className="min-w-0 px-3.5 py-2.5">
          <div className="text-xs text-zinc-500">成本合计</div>
          <div className="truncate font-semibold tabular-nums">{formatFen(preview.total_cost)}</div>
        </div>
        <div className="min-w-0 px-3.5 py-2.5">
          <div className="text-xs text-zinc-500">报价合计</div>
          <div className="truncate font-semibold tabular-nums">{formatFen(preview.total_price)}</div>
        </div>
        <div className="min-w-0 px-3.5 py-2.5">
          <div className="text-xs text-zinc-500">毛利率</div>
          <div className="truncate font-semibold tabular-nums">{formatPercent(preview.margin_rate)}</div>
        </div>
      </div>
      <ClientCosts costs={clientCostsOf(tier)} className="border-t border-zinc-200 px-3.5 py-2.5" />
      {changed ? (
        <p className="border-t border-zinc-100 px-3.5 py-2 text-xs text-zinc-500">
          单价和折扣不变；确认后由系统按产品目录重新计算，毛利不达标的报价单提交时需要主管审批。
        </p>
      ) : null}
    </div>
  )
}
