"use client"

import { CheckCircle2, Circle, Rocket, X } from "lucide-react"
import Link from "next/link"

import { Button } from "@/components/ui/button"
import { useDismissed } from "@/hooks/useDismissed"
import { useOnboarding } from "@/hooks/useOnboarding"
import { ONBOARDING_DISMISSED_KEY, progressPercent, showOnboarding } from "@/lib/onboarding"
import { cn } from "@/lib/utils"

/** 工作台顶部的上手清单：每一步点了就去对应页面；做完自动消失，也可以收起 */
export function OnboardingCard() {
  const [dismissed, dismiss] = useDismissed(ONBOARDING_DISMISSED_KEY)
  const query = useOnboarding(dismissed === false)
  const data = query.data
  if (dismissed !== false || !data || !showOnboarding(data, dismissed)) return null
  const next = data.steps.find((s) => !s.done)
  return (
    <section className="mb-3 rounded-lg border border-zinc-200 bg-white p-4" aria-label="上手清单">
      <div className="flex items-start gap-3">
        <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-zinc-100">
          <Rocket className="size-4 text-zinc-600" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-medium">
            开始使用 · 已完成 {data.done}/{data.total}
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-100">
            <div
              className="h-full rounded-full bg-zinc-900"
              style={{ width: `${progressPercent(data.done, data.total)}%` }}
            />
          </div>
        </div>
        <Button variant="ghost" size="icon-sm" aria-label="收起上手清单" title="收起，不再显示" onClick={dismiss}>
          <X />
        </Button>
      </div>
      <ol className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {data.steps.map((s) => (
          <li key={s.key}>
            <Link
              href={s.href}
              className={cn(
                "flex h-full gap-2 rounded-md border p-3 transition-colors hover:bg-zinc-50",
                s.key === next?.key ? "border-zinc-400" : "border-zinc-200",
              )}
            >
              {s.done ? (
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-label="已完成" />
              ) : (
                <Circle className="mt-0.5 size-4 shrink-0 text-zinc-300" aria-label="未完成" />
              )}
              <span className="min-w-0">
                <span className={cn("block", s.done && "text-zinc-400 line-through")}>{s.title}</span>
                {s.done ? null : <span className="mt-0.5 block text-xs leading-5 text-zinc-500">{s.detail}</span>}
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  )
}
