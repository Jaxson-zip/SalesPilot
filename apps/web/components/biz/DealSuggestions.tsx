"use client"

import { AlertTriangle, Lightbulb, Sparkles } from "lucide-react"
import Link from "next/link"

import { Button } from "@/components/ui/button"
import type { DealSuggestion } from "@/hooks/useSuggestions"
import { aiPrefillHref } from "@/lib/thread-history"
import { cn } from "@/lib/utils"

/**
 * 商机侧栏 / 客户页的「需要注意」：按这单的当前状态算出的建议（停滞、没有下一步、回款逾期……）。
 * 负责人可以「交给 AI」：带着这单打开 AI 工作台直接发出，写操作仍要在确认卡上确认。
 * 没有建议时整块不显示。
 */
export function DealSuggestions({
  rows,
  editable,
  showOpportunity = false,
}: {
  rows: DealSuggestion[] | undefined
  editable: boolean
  /** 客户页汇总多个商机时标出是哪一单 */
  showOpportunity?: boolean
}) {
  if (!rows?.length) return null
  return (
    <section aria-label="需要注意">
      <h3 className="mb-1.5 flex h-7 items-center text-zinc-500">需要注意</h3>
      <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
        {rows.map((s) => {
          const Icon = s.level === "warn" ? AlertTriangle : Lightbulb
          return (
            <li key={`${s.opportunity_id}-${s.kind}`} className="flex items-start gap-2.5 px-3 py-2.5">
              <Icon
                className={cn("mt-0.5 size-4 shrink-0", s.level === "warn" ? "text-orange-500" : "text-zinc-400")}
              />
              <div className="min-w-0 flex-1">
                <div className="text-sm text-zinc-800">
                  {showOpportunity ? <span className="text-zinc-500">{s.opportunity_name} · </span> : null}
                  {s.title}
                </div>
                {s.detail ? <div className="mt-0.5 truncate text-xs text-zinc-500">{s.detail}</div> : null}
              </div>
              {editable ? (
                <Button size="xs" variant="ghost" className="h-7 shrink-0 text-zinc-600" asChild>
                  <Link href={aiPrefillHref(s.prompt, s.opportunity_id, true)} aria-label={`交给 AI：${s.title}`}>
                    <Sparkles />
                    交给 AI
                  </Link>
                </Button>
              ) : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
