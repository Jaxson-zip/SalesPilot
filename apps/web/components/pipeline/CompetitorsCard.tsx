"use client"

import { Check, ChevronDown, Plus, Swords } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { BattleCardBody, CompetitorRecord } from "@/components/competitors/BattleCard"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { useCompetitors, useOpportunityCompetitors, useSetOpportunityCompetitors } from "@/hooks/useCompetitors"
import { cn } from "@/lib/utils"

/** 商机侧栏：遇到的竞品（负责人标注），点开直接看战卡话术 */
export function CompetitorsCard({ oppId, editable }: { oppId: string; editable: boolean }) {
  const mine = useOpportunityCompetitors(oppId)
  const all = useCompetitors()
  const set = useSetOpportunityCompetitors(oppId)
  const [open, setOpen] = useState<string | null>(null)
  const selected = mine.data ?? []
  const ids = selected.map((c) => c.id)
  const toggle = (id: string) => set.mutate(ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id])

  return (
    <section aria-label="竞争对手" className="space-y-2 text-sm">
      <div className="flex items-center gap-2">
        <h3 className="font-medium">竞争对手</h3>
        <Link href="/battlecards" className="text-xs text-zinc-400 hover:text-zinc-600">
          全部战卡
        </Link>
        {editable ? (
          <Popover>
            <PopoverTrigger asChild>
              <Button size="xs" variant="outline" className="ml-auto" disabled={set.isPending}>
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
        <ul className="space-y-1.5">
          {selected.map((c) => (
            <li key={c.id} className="rounded-lg border border-zinc-200">
              <button
                type="button"
                onClick={() => setOpen(open === c.id ? null : c.id)}
                aria-expanded={open === c.id}
                aria-label={`${c.name} 应对话术`}
                className="flex w-full items-start gap-2 p-2.5 text-left"
              >
                <Swords className="mt-0.5 size-4 shrink-0 text-zinc-400" />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{c.name}</span>
                  <CompetitorRecord c={c} />
                </span>
                <ChevronDown
                  className={cn(
                    "mt-0.5 size-4 shrink-0 text-zinc-400 transition-transform",
                    open !== c.id && "-rotate-90",
                  )}
                />
              </button>
              {open === c.id ? (
                <div className="border-t border-zinc-100 p-2.5">
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
