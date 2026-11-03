"use client"

import {
  Boxes,
  Calendar,
  Coins,
  ExternalLink,
  FilePlus,
  FileText,
  Loader2,
  Lock,
  NotebookPen,
  Package,
  Percent,
  Receipt,
  Sparkles,
  Target,
  User,
  UserRoundCheck,
} from "lucide-react"
import Link from "next/link"
import { useState } from "react"
import {
  StageReadOnly,
  StageBar,
  Profit,
  RecentActivities,
  KeyContacts,
} from "@/components/pipeline/OpportunitySheetParts"

import { PasteNotesDialog } from "@/components/agent/PasteNotesDialog"
import { Chip } from "@/components/biz/Chip"
import { FieldRow } from "@/components/biz/FieldRow"
import { FormSheet } from "@/components/biz/FormSheet"
import { InlineEditRow } from "@/components/biz/InlineEditRow"
import { QueryError } from "@/components/biz/QueryStatus"
import { PackName } from "@/components/biz/PackName"
import { Tag } from "@/components/biz/Tag"
import { DealSuggestions } from "@/components/biz/DealSuggestions"
import { CompetitorsCard } from "@/components/pipeline/CompetitorsCard"
import { MeddicCard } from "@/components/pipeline/MeddicCard"
import { RequirementSummary } from "@/components/pipeline/RequirementSummary"
import { SubjectTasks } from "@/components/tasks/TaskList"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useFollowups } from "@/hooks/useFollowups"
import { useOpportunity, useUpdateOpportunity } from "@/hooks/useOpportunities"
import { useOpportunitySuggestions } from "@/hooks/useSuggestions"
import { formatFen, formatRelative, ownerName } from "@/lib/format"
import { labelOf, QUOTE_STATUS_META } from "@/lib/labels"
import { customerHref, opportunityExpensesHref } from "@/lib/links"
import { isFinalStage } from "@/lib/pipeline"
import { staleText } from "@/lib/tasks"
import { aiPrefillHref, opportunityPrompt } from "@/lib/thread-history"
import type { OpportunityDetail, OpportunityItem, OpportunityStage } from "@/types/api"

function Fields({
  o,
  editable,
}: {
  o: OpportunityItem & Partial<Pick<OpportunityDetail, "quotes" | "expenses" | "profit">>
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
      {o.profit ? null : (
        <FieldRow icon={Receipt} label="跟单费用">
          {o.expenses?.count ? (
            <Link href={opportunityExpensesHref(o.id)} className="tabular-nums hover:underline">
              {[
                o.expenses.approved ? `已批 ${formatFen(o.expenses.approved)}` : "",
                o.expenses.pending ? `审批中 ${formatFen(o.expenses.pending)}` : "",
              ]
                .filter(Boolean)
                .join(" · ")}
            </Link>
          ) : (
            "—"
          )}
        </FieldRow>
      )}
      {o.profit ? <Profit p={o.profit} oppId={o.id} /> : null}
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
  focusTaskId,
}: {
  opp: OpportunityItem | null
  /** 从通知 / 待办点进来时要定位的任务 */
  focusTaskId?: string | null
  /** 本人负责的商机才能切换阶段、出方案 */
  editable: boolean
  onClose: () => void
  onStageChange: (opp: OpportunityItem, to: OpportunityStage) => void
  changing?: boolean
}) {
  const detail = useOpportunity(opp?.id ?? null)
  const suggestions = useOpportunitySuggestions(opp?.id ?? null)
  const o = detail.data ?? opp
  // 赢单 / 输单后不再出报价、出方案（后端也会拦）；输单的待办已随输单自动完成，不再提示安排下一步
  const open = o ? !isFinalStage(o.stage) : false
  const lost = o?.stage === "lost"
  const [pasting, setPasting] = useState(false)
  // 出方案直接发给 AI：带上这个商机的跟进记录（没有就用这个客户最近的）
  // 跟进记录还没读到时按钮先转圈，免得发出「还没有跟进记录」；读失败就不带这部分
  const notes = useFollowups(o?.customer.id ?? "", 30)
  const followups = notes.data ?? []
  const forOpp = followups.filter((f) => f.opportunity_id === o?.id)
  const solutionHref = o
    ? aiPrefillHref(
        opportunityPrompt({
          customer: o.customer.name,
          name: o.name,
          amount: o.amount,
          followups: notes.isError ? undefined : forOpp.length ? forOpp : followups.filter((f) => !f.opportunity_id),
        }),
        o.id,
        true,
      )
    : "/ai"
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
              <Button variant="outline" onClick={() => setPasting(true)}>
                <NotebookPen />
                粘贴纪要
              </Button>
            ) : null}
            {editable && open ? (
              <Button variant="outline" asChild>
                <Link href={`/quotes/new?opp=${encodeURIComponent(o.id)}`}>
                  <FilePlus />
                  手动报价
                </Link>
              </Button>
            ) : null}
            {!open ? null : editable && notes.isPending ? (
              <Button disabled>
                <Loader2 className="animate-spin" />
                出方案
              </Button>
            ) : editable ? (
              <Button asChild>
                <Link href={solutionHref}>
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
                <Link href={customerHref(o.customer.id)} className="inline-flex min-w-0" title="打开客户">
                  <Chip name={o.customer.name} logo={o.customer.name.slice(0, 1)} />
                </Link>
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
          <DealSuggestions rows={suggestions.data} editable={editable} />
          <Fields o={o} editable={editable} />
          <RequirementSummary oppId={o.id} oppName={o.name} editable={editable} />
          <MeddicCard oppId={o.id} editable={editable} />
          <CompetitorsCard oppId={o.id} editable={editable} />
          {/* U9：去掉固定文字的「下一步建议」，换成真实的下一步任务（v3 §12） */}
          {lost ? null : (
            <SubjectTasks
              subjectType="opportunity"
              subjectId={o.id}
              subjectName={o.name}
              editable={editable}
              focusId={focusTaskId}
            />
          )}
          {detail.isPending ? (
            <Skeleton className="h-24 w-full" />
          ) : detail.isError ? (
            <QueryError error={detail.error} onRetry={() => void detail.refetch()} feature="商机详情" />
          ) : (
            <RecentActivities detail={detail.data} />
          )}
          {editable ? (
            <PasteNotesDialog
              open={pasting}
              onOpenChange={setPasting}
              customer={o.customer.name}
              opportunity={{ id: o.id, name: o.name }}
            />
          ) : null}
        </>
      ) : null}
    </FormSheet>
  )
}
