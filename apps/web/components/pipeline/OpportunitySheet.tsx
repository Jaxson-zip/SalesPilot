"use client"

import {
  ArrowRight,
  Boxes,
  Calendar,
  Coins,
  ExternalLink,
  FileText,
  Lock,
  Package,
  Percent,
  Sparkles,
  Target,
  User,
} from "lucide-react"
import Link from "next/link"

import { Chip } from "@/components/biz/Chip"
import { FieldRow } from "@/components/biz/FieldRow"
import { FormSheet } from "@/components/biz/FormSheet"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useOpportunity } from "@/hooks/useOpportunities"
import { formatFen, formatRelative } from "@/lib/format"
import { activityActionLabel, labelOf, QUOTE_STATUS_META, STAGE_META, STAGE_ORDER } from "@/lib/labels"
import { isFinalStage, stageBarState } from "@/lib/pipeline"
import { cn } from "@/lib/utils"
import type { OpportunityDetail, OpportunityItem, OpportunityStage } from "@/types/api"
import { PackName } from "@/components/biz/PackName"

const BAR_CLS = {
  done: "bg-zinc-200 text-zinc-700",
  current: "bg-zinc-900 font-medium text-white",
  todo: "bg-zinc-100 text-zinc-400 hover:bg-zinc-200 hover:text-zinc-600",
}

function StageBar({
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
          {final ? `已${STAGE_META[stage].label}，不能再切换` : "点击切换，变更会写入时间线"}
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

function Fields({ o }: { o: OpportunityItem & Partial<Pick<OpportunityDetail, "quotes">> }) {
  return (
    <div className="-mx-1.5">
      <FieldRow icon={Coins} label="金额">
        <span className="tabular-nums">{formatFen(o.amount)}</span>
      </FieldRow>
      <FieldRow icon={Percent} label="赢率">
        <span className="tabular-nums">{o.win_rate}%</span>
      </FieldRow>
      <FieldRow icon={Calendar} label="预计成交">
        {o.expected_close_date ?? "—"}
      </FieldRow>
      <FieldRow icon={Package} label="产品线">
        {o.product_line?.name ?? "—"}
      </FieldRow>
      <FieldRow icon={Boxes} label="行业包">
        <span className="inline-flex items-center gap-1.5 text-zinc-600">
          <PackName id={o.product_line?.pack} />
          <Lock className="size-3 text-zinc-400" />
          <span className="text-xs text-zinc-400">由产品线自动匹配</span>
        </span>
      </FieldRow>
      <FieldRow icon={User} label="负责人">
        <Chip name={o.owner.name} />
      </FieldRow>
      <FieldRow icon={FileText} label="关联报价">
        {o.quotes?.length ? (
          <span className="inline-flex flex-wrap items-center gap-1.5">
            {o.quotes.slice(0, 2).map((q) => (
              <Link key={q.id} href={`/quotes/${q.id}`} className="inline-flex items-center gap-1.5 hover:underline">
                {q.code}
                <Tag color={labelOf(QUOTE_STATUS_META, q.status).color}>
                  {labelOf(QUOTE_STATUS_META, q.status).label}
                </Tag>
              </Link>
            ))}
          </span>
        ) : (
          "—"
        )}
      </FieldRow>
    </div>
  )
}

function RecentActivities({ detail }: { detail: OpportunityDetail | undefined }) {
  const list = detail?.activities.slice(0, 5) ?? []
  return (
    <div>
      <div className="mb-2 text-zinc-500">最近动态</div>
      {list.length === 0 ? <div className="text-zinc-400">暂无动态</div> : null}
      {list.map((a) => {
        const isAi = a.source === "agent" || a.actor === null
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

/** OpportunitySheet：阶段条、字段、AI 下一步建议、最近动态 */
export function OpportunitySheet({
  opp,
  onClose,
  onStageChange,
  changing,
}: {
  opp: OpportunityItem | null
  onClose: () => void
  onStageChange: (opp: OpportunityItem, to: OpportunityStage) => void
  changing?: boolean
}) {
  const detail = useOpportunity(opp?.id ?? null)
  const o = detail.data ?? opp
  return (
    <FormSheet
      open={opp !== null}
      onOpenChange={(v) => !v && onClose()}
      title="商机"
      footer={
        o ? (
          <>
            <Button variant="outline" asChild>
              <Link href={`/customers/${o.customer.id}`}>
                <ExternalLink />
                打开客户页面
              </Link>
            </Button>
            <Button asChild>
              <Link href="/ai">
                <Sparkles />
                出方案
              </Link>
            </Button>
          </>
        ) : null
      }
    >
      {o ? (
        <>
          <div className="flex items-start gap-3">
            <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg bg-zinc-100">
              <Target className="size-5 text-zinc-600" />
            </span>
            <div className="min-w-0">
              <div className="truncate text-base font-semibold">{o.name}</div>
              <div className="mt-1 flex min-w-0 items-center gap-1.5 text-zinc-500">
                <Chip name={o.customer.name} logo={o.customer.name.slice(0, 1)} />
                <span className="shrink-0">· 更新于 {formatRelative(o.updated_at)}</span>
              </div>
            </div>
          </div>
          <StageBar stage={o.stage} disabled={changing} onChange={(s) => onStageChange(o, s)} />
          <Fields o={o} />
          <div className="flex gap-2 rounded-lg border border-violet-200 bg-violet-50/60 px-3 py-2.5 text-violet-900">
            <Sparkles className="text-ai mt-0.5 size-4 shrink-0" />
            <div className="min-w-0">
              <div className="font-medium">下一步建议</div>
              <div className="mt-0.5 text-violet-800/90">
                在 AI 方案工作台询问「{o.name} 下一步怎么推进」，AI 会结合跟进记录和行业包给出建议。
              </div>
            </div>
          </div>
          {detail.isPending ? (
            <Skeleton className="h-24 w-full" />
          ) : detail.isError ? (
            <QueryError error={detail.error} onRetry={() => void detail.refetch()} feature="商机详情" />
          ) : (
            <RecentActivities detail={detail.data} />
          )}
        </>
      ) : null}
    </FormSheet>
  )
}
