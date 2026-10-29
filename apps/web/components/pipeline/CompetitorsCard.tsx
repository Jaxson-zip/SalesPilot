"use client"

import { Check, ChevronRight, Plus, Swords } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { BattleCardBody, CompetitorRecord } from "@/components/competitors/BattleCard"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { useCompetitors, useOpportunityCompetitors, useSetOpportunityCompetitors } from "@/hooks/useCompetitors"
import { cn } from "@/lib/utils"

/** 商机侧栏：遇到的竞品（负责人标注），点开直接看战卡话术；版式与「下一步」「最近动态」一致 */
export function CompetitorsCard({ oppId, editable }: { oppId: string; editable: boolean }) {
  const mine = useOpportunityCompetitors(oppId)
  const all = useCompetitors()
  const set = useSetOpportunityCompetitors(oppId)
  const [open, setOpen] = useState<string | null>(null)
  const selected = mine.data ?? []
  const ids = selected.map((c) => c.id)
  const toggle = (id: string) => set.mutate(ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id])

  return (
    <section aria-label="竞争对手">
      <div className="mb-1.5 flex h-7 items-center gap-2">
        <h3 className="text-zinc-500">竞争对手</h3>
        <Link href="/battlecards" className="text-xs text-zinc-400 hover:text-zinc-600 hover:underline">
          全部战卡
        </Link>
        {editable ? (
          <Popover>
            <PopoverTrigger asChild>
              <Button size="xs" variant="ghost" className="ml-auto h-7 text-zinc-600" disabled={set.isPending}>
                <Plus />
                标注竞品
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-64 p-1">
              <ul aria-label="选择竞品">
                {(all.data ?? []).map((c) => {
                  const on = ids.includes(c.id)
                  return (
                    <li key={c.id}>
                      <button
                        type="button"
                        role="menuitemcheckbox"
                        aria-checked={on}
                        onClick={() => toggle(c.id)}
                        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-zinc-100"
                      >
                        <Check className={cn("size-4 shrink-0", on ? "opacity-100" : "opacity-0")} />
                        <span className="truncate">{c.name}</span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </PopoverContent>
          </Popover>
        ) : null}
      </div>
      {selected.length === 0 ? (
        <p className="text-zinc-400">{editable ? "客户在比较别家时标注一下，就能直接看到应对话术。" : "未标注竞品"}</p>
      ) : (
        <ul className="space-y-0.5">
          {selected.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => setOpen(open === c.id ? null : c.id)}
                aria-expanded={open === c.id}
                aria-label={`${c.name} 应对话术`}
                className="flex w-full items-start gap-2.5 rounded-md px-1 py-1.5 text-left hover:bg-zinc-50"
              >
                <Swords className="mt-0.5 size-4 shrink-0 text-zinc-400" />
                <span className="min-w-0 flex-1">
                  <span className="block">{c.name}</span>
                  <CompetitorRecord c={c} />
                </span>
                <span className="mt-0.5 flex shrink-0 items-center text-xs text-zinc-400">
                  {open === c.id ? "收起" : "应对话术"}
                  <ChevronRight className={cn("size-4 transition-transform", open === c.id && "rotate-90")} />
                </span>
              </button>
              {open === c.id ? (
                <div className="mt-1 mb-2 ml-7">
                  <BattleCardBody c={c} compact />
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
