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
  UserRoundCheck,
} from "lucide-react"
import Link from "next/link"

import { Chip } from "@/components/biz/Chip"
import { FieldRow } from "@/components/biz/FieldRow"
import { FormSheet } from "@/components/biz/FormSheet"
import { InlineEditRow } from "@/components/biz/InlineEditRow"
import { QueryError } from "@/components/biz/QueryStatus"
import { PackName } from "@/components/biz/PackName"
import { Tag } from "@/components/biz/Tag"
import { CompetitorsCard } from "@/components/pipeline/CompetitorsCard"
import { MeddicCard } from "@/components/pipeline/MeddicCard"
import { RequirementSummary } from "@/components/pipeline/RequirementSummary"
import { SubjectTasks } from "@/components/tasks/TaskList"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useContacts } from "@/hooks/useFollowups"
import { useOpportunity, useUpdateOpportunity } from "@/hooks/useOpportunities"
import { formatFen, formatRelative, ownerName } from "@/lib/format"
import {
  activityActionLabel,
  CONTACT_ROLE_META,
  KEY_CONTACT_ROLES,
  labelOf,
  QUOTE_STATUS_META,
  STAGE_META,
  STAGE_ORDER,
} from "@/lib/labels"
import { isFinalStage, stageBarState } from "@/lib/pipeline"
import { staleText } from "@/lib/tasks"
import { aiPrefillHref, solutionPrompt } from "@/lib/thread-history"
import { cn } from "@/lib/utils"
import type { OpportunityDetail, OpportunityItem, OpportunityStage } from "@/types/api"

const BAR_CLS = {
  done: "bg-zinc-200 text-zinc-700",
  current: "bg-zinc-900 font-medium text-white",
  todo: "bg-zinc-100 text-zinc-400 hover:bg-zinc-200 hover:text-zinc-600",
}

/** 无权切换阶段时只显示当前阶段 */
function StageReadOnly({ stage }: { stage: OpportunityStage }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-zinc-500">阶段</span>
      <Tag color={STAGE_META[stage].color}>{STAGE_META[stage].label}</Tag>
      <span className="ml-auto text-xs text-zinc-400">仅负责人可切换阶段</span>
    </div>
  )
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
function KeyContacts({ customerId }: { customerId: string }) {
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

function Fields({
  o,
  editable,
}: {
  o: OpportunityItem & Partial<Pick<OpportunityDetail, "quotes">>
  editable: boolean
}) {
  const update = useUpdateOpportunity(o.id)
  // 赢单 / 输单后金额等字段不再修改
  const canEdit = editable && !isFinalStage(o.stage)
  return (
    <div>
      <InlineEditRow
        icon={Coins}
        label="金额"
        kind="money"
        required
        value={o.amount}
        editable={canEdit}
        display={<span className="tabular-nums">{formatFen(o.amount)}</span>}
        onSave={(v) => update.mutateAsync({ amount: v as number })}
      />
      <InlineEditRow
        icon={Percent}
        label="赢率"
        kind="int"
        min={0}
        max={100}
        required
        value={o.win_rate}
        editable={canEdit}
        display={<span className="tabular-nums">{o.win_rate}%</span>}
        onSave={(v) => update.mutateAsync({ win_rate: v as number })}
      />
      <InlineEditRow
        icon={Calendar}
        label="预计成交"
        kind="date"
        value={o.expected_close_date}
        editable={canEdit}
        display={o.expected_close_date ?? "—"}
        onSave={(v) => update.mutateAsync({ expected_close_date: v as string | null })}
      />
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
        <Chip name={ownerName(o.owner)} />
      </FieldRow>
      <FieldRow icon={UserRoundCheck} label="关键人">
        <KeyContacts customerId={o.customer.id} />
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

/** OpportunitySheet：阶段条、字段（含停滞提醒）、下一步任务、最近动态 */
export function OpportunitySheet({
  opp,
  editable,
  onClose,
  onStageChange,
  changing,
}: {
  opp: OpportunityItem | null
  /** 本人负责的商机才能切换阶段、出方案 */
  editable: boolean
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
            {editable ? (
              <Button asChild>
                <Link href={aiPrefillHref(solutionPrompt(o.customer.name, o.name), o.id)}>
                  <Sparkles />
                  出方案
                </Link>
              </Button>
            ) : null}
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
              {staleText(o) ? (
                <div className="mt-1.5">
                  <Tag color="orange">{staleText(o)}</Tag>
                </div>
              ) : null}
            </div>
          </div>
          {editable ? (
            <StageBar stage={o.stage} disabled={changing} onChange={(s) => onStageChange(o, s)} />
          ) : (
            <StageReadOnly stage={o.stage} />
          )}
          <Fields o={o} editable={editable} />
          <RequirementSummary oppId={o.id} />
          <MeddicCard oppId={o.id} editable={editable} />
          <CompetitorsCard oppId={o.id} editable={editable} />
          {/* U9：去掉固定文字的「下一步建议」，换成真实的下一步任务（v3 §12） */}
          <SubjectTasks subjectType="opportunity" subjectId={o.id} subjectName={o.name} editable={editable} />
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
