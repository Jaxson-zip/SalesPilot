import { Tag } from "@/components/biz/Tag"
import { formatFen, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { SolutionTier } from "@/types/api"

/** 三档方案卡片：推荐档黑色描边；<640 单列 */
export function TierCards({ tiers }: { tiers: SolutionTier[] }) {
  return (
    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
      {tiers.map((t) => (
        <div
          key={t.name}
          className={cn(
            "min-w-0 rounded-xl border bg-white p-3.5",
            t.recommended ? "border-zinc-900 ring-1 ring-zinc-900" : "border-zinc-200",
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
      ))}
    </div>
  )
}
