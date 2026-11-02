"use client"

import { ArrowRight, Sparkles } from "lucide-react"
import Link from "next/link"

import { Tag } from "@/components/biz/Tag"
import { Skeleton } from "@/components/ui/skeleton"
import { useContacts } from "@/hooks/useFollowups"
import { formatFen, formatRelative } from "@/lib/format"
import { activityActionLabel, CONTACT_ROLE_META, KEY_CONTACT_ROLES, STAGE_META, STAGE_ORDER } from "@/lib/labels"
import { opportunityExpensesHref } from "@/lib/links"
import { activityActor } from "@/lib/timeline"
import { isFinalStage, stageBarState } from "@/lib/pipeline"
import { cn } from "@/lib/utils"
import type { OpportunityDetail, OpportunityProfit, OpportunityStage } from "@/types/api"

export const BAR_CLS = {
  done: "bg-zinc-200 text-zinc-700",
  current: "bg-zinc-900 font-medium text-white",
  todo: "bg-zinc-100 text-zinc-400 hover:bg-zinc-200 hover:text-zinc-600",
}

/** 无权切换阶段时只显示当前阶段 */
export function StageReadOnly({ stage }: { stage: OpportunityStage }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-zinc-500">阶段</span>
      <Tag color={STAGE_META[stage].color}>{STAGE_META[stage].label}</Tag>
      <span className="ml-auto text-xs text-zinc-400">仅负责人可切换阶段</span>
    </div>
  )
}

export function StageBar({
  stage,
  onChange,
  disabled,
}: {
  stage: OpportunityStage
  onChange: (s: OpportunityStage) => void
  disabled?: boolean
}) {
  const final = isFinalStage(stage)
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-zinc-500">阶段</span>
        <span className="text-xs text-zinc-400">
          {final ? `已${STAGE_META[stage].label}，不能再切换` : "点击切换（可撤销），赢单需确认"}
        </span>
      </div>
      <div className="flex gap-1">
        {STAGE_ORDER.map((s) => (
          <button
            key={s}
            type="button"
            disabled={final || disabled || s === stage}
            onClick={() => onChange(s)}
            className={cn("h-7 min-w-0 flex-1 truncate rounded-md px-1 text-xs", BAR_CLS[stageBarState(stage, s)])}
          >
            {STAGE_META[s].label}
          </button>
        ))}
      </div>
      {stage === "lost" ? (
        <div className="mt-1.5">
          <Tag color="red">{STAGE_META.lost.label}</Tag>
        </div>
      ) : !final ? (
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange("lost")}
          className="mt-1.5 text-xs text-zinc-400 hover:text-red-600"
        >
          标记为输单…
        </button>
      ) : null}
    </div>
  )
}

/** 关键人（B7）：客户联系人里的决策人、影响者、技术把关 */
export function KeyContacts({ customerId }: { customerId: string }) {
  const q = useContacts(customerId)
  if (q.isPending) return <Skeleton className="h-5 w-32" />
  const key = (q.data ?? []).filter((c) => c.role && KEY_CONTACT_ROLES.includes(c.role))
  if (key.length === 0)
    return (
      <Link href={`/customers/${encodeURIComponent(customerId)}`} className="text-zinc-400 hover:underline">
        未标注，去客户详情添加
      </Link>
    )
  return (
    <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
      {key.map((c) => (
        <span key={c.id} className="inline-flex items-center gap-1" title={c.title ?? undefined}>
          {c.name}
          <span className="text-xs text-zinc-500">{CONTACT_ROLE_META[c.role!].label}</span>
        </span>
      ))}
    </span>
  )
}

/** 这单赚多少：报价毛利 − 预估提成 − 跟单费用 */
export function Profit({ p, oppId }: { p: OpportunityProfit; oppId: string }) {
  const rows: [string, number][] = [
    ["报价毛利", p.gross],
    ["预估提成", -p.commission],
    ["跟单费用", -p.expenses],
  ]
  return (
    <section aria-label="这单赚多少" className="mt-3 rounded-lg border border-zinc-200 p-3">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="font-medium">这单赚多少</span>
        <Link href={`/quotes/${p.quote_id}`} className="text-xs text-zinc-500 hover:underline">
          {p.basis === "accepted" ? "按成交报价" : "按最新报价估算"} {p.quote_code}
        </Link>
      </div>
      <dl className="space-y-1 tabular-nums">
        {rows.map(([label, v]) => (
          <div key={label} className="flex justify-between text-zinc-600">
            <dt>
              {label === "跟单费用" && v < 0 ? (
                <Link href={opportunityExpensesHref(oppId)} className="hover:underline">
                  {label}
                </Link>
              ) : (
                label
              )}
            </dt>
            <dd>{v < 0 ? `−${formatFen(-v)}` : formatFen(v)}</dd>
          </div>
        ))}
        <div className="flex justify-between border-t border-zinc-100 pt-1 font-medium">
          <dt>实际赚</dt>
          <dd className={p.net < 0 ? "text-red-600" : undefined}>
            {p.net < 0 ? `−${formatFen(-p.net)}` : formatFen(p.net)}
            {p.price ? (
              <span className="ml-1.5 text-xs font-normal text-zinc-500">{((p.net / p.price) * 100).toFixed(1)}%</span>
            ) : null}
          </dd>
        </div>
      </dl>
    </section>
  )
}

export function RecentActivities({ detail }: { detail: OpportunityDetail | undefined }) {
  const list = detail?.activities.slice(0, 5) ?? []
  return (
    <div>
      <div className="mb-2 text-zinc-500">最近动态</div>
      {list.length === 0 ? <div className="text-zinc-400">暂无动态</div> : null}
      {list.map((a) => {
        const isAi = activityActor(a) === "ai"
        return (
          <div key={a.id} className="flex h-8 items-center gap-2.5">
            <span
              className={cn(
                "inline-flex size-5 shrink-0 items-center justify-center rounded-full border border-zinc-200",
                isAi ? "text-ai" : "text-zinc-500",
              )}
            >
              {isAi ? <Sparkles className="size-3" /> : <ArrowRight className="size-3" />}
            </span>
            <span className="min-w-0 flex-1 truncate" title={a.content ?? undefined}>
              {activityActionLabel(a.action, a.subject_type)}
              {a.content ? `：${a.content}` : ""}
            </span>
            <span className="shrink-0 text-xs text-zinc-400">{formatRelative(a.created_at)}</span>
          </div>
        )
      })}
    </div>
  )
}
