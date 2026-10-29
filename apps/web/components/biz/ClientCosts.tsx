import { CLIENT_COSTS_NOTE, CLIENT_COSTS_TITLE, costAmount, costSummary, type ClientCost } from "@/lib/client-costs"
import { cn } from "@/lib/utils"

/** 运营期客户自付费用：方案物料卡、报价单详情和打印页共用；没有时不渲染 */
export function ClientCosts({ costs, className }: { costs: ClientCost[]; className?: string }) {
  if (!costs.length) return null
  return (
    <section aria-label={CLIENT_COSTS_TITLE} className={cn("text-sm", className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <span className="font-medium">{CLIENT_COSTS_TITLE}</span>
        <span className="text-xs text-zinc-500 tabular-nums">约 {costSummary(costs)}</span>
      </div>
      <p className="mt-0.5 text-xs text-zinc-500">{CLIENT_COSTS_NOTE}</p>
      <ul className="mt-1.5 divide-y divide-zinc-100">
        {costs.map((c) => (
          <li key={c.name} className="flex items-start justify-between gap-3 py-1.5">
            <div className="min-w-0">
              <div className="break-words">{c.name}</div>
              {c.note ? <div className="text-xs text-zinc-500">{c.note}</div> : null}
            </div>
            <span className="shrink-0 tabular-nums">{costAmount(c)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
