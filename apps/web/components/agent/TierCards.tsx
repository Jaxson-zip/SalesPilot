import { Tag } from "@/components/biz/Tag"
import { formatFen, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { SolutionTier } from "@/types/api"

/**
 * 三档方案卡片：选中档黑色描边（默认推荐档）；<640 单列。
 * 传了 onSelect 时可以点选另一档：下面的物料清单和「生成报价单」确认卡跟着切换。
 */
export function TierCards({
  tiers,
  selected,
  onSelect,
}: {
  tiers: SolutionTier[]
  /** 选中档位的 key；不传时推荐档为选中 */
  selected?: string
  onSelect?: (key: string) => void
}) {
  const isSelected = (t: SolutionTier) => (selected ? t.key === selected : Boolean(t.recommended))
  return (
    <div className="space-y-1.5">
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
        {tiers.map((t) => {
          const on = isSelected(t)
          const pick = onSelect && t.key ? () => onSelect(t.key as string) : undefined
          return (
            <div
              key={t.name}
              role={pick ? "button" : undefined}
              tabIndex={pick ? 0 : undefined}
              aria-pressed={pick ? on : undefined}
              aria-label={pick ? `选择${t.name}` : undefined}
              onClick={pick}
              onKeyDown={
                pick
                  ? (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault()
                        pick()
                      }
                    }
                  : undefined
              }
              className={cn(
                "min-w-0 rounded-xl border bg-white p-3.5",
                on ? "border-zinc-900 ring-1 ring-zinc-900" : "border-zinc-200",
                pick &&
                  "cursor-pointer transition-colors hover:border-zinc-400 focus-visible:ring-2 focus-visible:ring-zinc-400 focus-visible:outline-none",
              )}
            >
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{t.name}</span>
                {t.recommended ? <Tag color="purple">推荐</Tag> : null}
              </div>
              <div className="mt-2 text-lg font-semibold tabular-nums">{formatFen(t.price)}</div>
              <div className="text-xs text-zinc-500">毛利 {formatPercent(t.margin)}</div>
              <div className="mt-2.5 border-t border-zinc-100 pt-2.5 text-xs leading-5 text-zinc-500">{t.spec}</div>
            </div>
          )
        })}
      </div>
      {onSelect ? <p className="text-xs text-zinc-500">点选档位可以切换方案，确认时按选中的档位生成报价单</p> : null}
    </div>
  )
}
