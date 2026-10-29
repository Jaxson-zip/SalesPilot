"use client"

import type { Competitor } from "@/hooks/useCompetitors"
import { cn } from "@/lib/utils"

function Points({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <div className="min-w-0">
      <div className="mb-1 text-xs text-zinc-500">{title}</div>
      <ul className="list-disc space-y-0.5 pl-4 text-zinc-700 marker:text-zinc-300">
        {items.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
    </div>
  )
}

/** 战绩：只列有数的项（进行中 / 赢 / 输），以及最近的输单原因（输单原因回流到战卡） */
export function CompetitorRecord({ c }: { c: Competitor }) {
  const { open, won, lost, lost_reasons } = c.stats
  if (!open && !won && !lost) return <span className="text-xs text-zinc-400">还没有商机标注过</span>
  const parts = [open && `进行中 ${open}`, won && `赢 ${won}`, lost && `输 ${lost}`].filter(Boolean)
  return (
    <span className="text-xs text-zinc-500">
      交手 {open + won + lost} 次 · {parts.join(" · ")}
      {lost_reasons.length ? <span className="block text-zinc-400">最近输单：{lost_reasons.join("；")}</span> : null}
    </span>
  )
}

/** 一张战卡的完整内容：常见说法与应对放最前（现场最常用），其次是怎么赢、弱点、优势 */
export function BattleCardBody({ c, compact }: { c: Competitor; compact?: boolean }) {
  return (
    <div className="space-y-3 text-sm">
      {c.objections.length ? (
        <div>
          <div className="mb-1.5 text-xs text-zinc-500">客户这么说时</div>
          <ul className="space-y-2.5">
            {c.objections.map((o) => (
              <li key={o.say} className="border-l-2 border-zinc-200 pl-3">
                <div className="text-zinc-500">「{o.say}」</div>
                <div className="mt-0.5 text-zinc-900">{o.respond}</div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className={cn("grid gap-3", !compact && "sm:grid-cols-3")}>
        <Points title="我们怎么赢" items={c.win_tactics} />
        <Points title="他们的弱点" items={c.weaknesses} />
        <Points title="他们的优势" items={c.strengths} />
      </div>
    </div>
  )
}
