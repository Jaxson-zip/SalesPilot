"use client"

import { Check, Clock, FileText, List, Printer, RotateCcw, Send, Stamp, X, type LucideIcon } from "lucide-react"
import { useParams } from "next/navigation"
import { useState } from "react"

import { BomTable } from "@/components/agent/BomTable"
import { RemindButton } from "@/components/approvals/RemindButton"
import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { Crumb, FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { RecordTabs } from "@/components/biz/RecordTabs"
import { QuoteAdjust } from "@/components/quotes/QuoteAdjust"
import { QuoteShareButton } from "@/components/quotes/QuoteShareButton"
import { ApprovalRecords, QuoteFields, QuoteTimeline } from "@/components/quotes/QuotePanels"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { usePermissions } from "@/hooks/usePermissions"
import { useQuote, useQuoteAction } from "@/hooks/useQuotes"
import { pendingApprovalId } from "@/lib/approvals"
import { quoteActionConfirm } from "@/lib/confirm-texts"
import { formatRelative } from "@/lib/format"
import { availableQuoteActions, primaryQuoteAction, QUOTE_ACTIONS, quoteToBom } from "@/lib/quote-actions"
import { canShareQuote } from "@/lib/share"
import { canPrintQuote } from "@/lib/quote-print"
import type { QuoteAction, QuoteDetail } from "@/types/api"

/** 报价内容变化（保存调整后后端重新计算）时重新挂载调价面板 */
function adjustKey(q: QuoteDetail): string {
  return [
    q.total_price,
    q.discount_rate ?? 0,
    ...q.items.map((it) => `${it.sku}:${it.qty}:${it.unit_price}:${it.name}:${it.category}`),
  ].join("|")
}

const ACTION_ICON: Record<QuoteAction, LucideIcon> = {
  submit: Stamp,
  send: Send,
  accept: Check,
  reject: X,
  renew: RotateCcw,
}

/** 报价单记录页：左字段 + 右标签页（物料清单 / 时间线 / 审批记录）；按当前状态只显示可用操作 */
export default function QuoteDetailPage() {
  const { id } = useParams<{ id: string }>()
  const quoteId = decodeURIComponent(id)
  const { role } = useSession()
  const { canEdit, canApprove } = usePermissions()
  const query = useQuote(quoteId)
  const action = useQuoteAction(quoteId)
  const [tab, setTab] = useState("bom")
  const { ask, dialog } = useConfirmAction()
  const q = query.data
  // 主管：待审批的报价直接跳到审批列表那一条处理
  const approvalId = q ? pendingApprovalId(q, canApprove) : null

  // 发送客户 / 客户接受 / 客户拒绝不可撤回：先确认；提交可被主管驳回，直接执行
  const run = (a: QuoteAction) => {
    const copy = quoteActionConfirm(a)
    if (!copy) return action.mutate(a)
    ask({ ...copy, onConfirm: () => action.mutate(a) })
  }

  // 报价状态按钮只给负责人本人（契约 §0）
  const actions = q && canEdit(q.owner?.id) ? availableQuoteActions(q.status, q.expired) : []
  const primary = q ? primaryQuoteAction(q.status, q.expired) : null
  const buttons = actions.map((a) => {
    const Icon = ACTION_ICON[a]
    return (
      <Button
        key={a}
        size="sm"
        variant={a === primary ? "default" : "outline"}
        // 没有客户的报价单不能提交（后端 42201 quote_no_customer），左侧提示原因
        disabled={action.isPending || (a === "submit" && !q?.customer)}
        onClick={() => run(a)}
        title={QUOTE_ACTIONS[a].label}
        className="max-sm:w-8 max-sm:px-0"
      >
        <Icon />
        <span className="max-sm:hidden">{QUOTE_ACTIONS[a].label}</span>
      </Button>
    )
  })

  let body
  if (query.isPending) {
    body = (
      <div className="space-y-3 p-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  } else if (query.isError) {
    body = (
      <QueryError
        error={query.error}
        onRetry={() => void query.refetch()}
        retrying={query.isFetching}
        feature="报价单详情"
      />
    )
  } else {
    const quote = query.data
    body = (
      <div className="flex min-h-0 flex-1 flex-col overflow-x-hidden overflow-y-auto lg:flex-row lg:overflow-hidden">
        <div className="shrink-0 border-b border-zinc-200 p-4 lg:w-[340px] lg:overflow-y-auto lg:border-r lg:border-b-0">
          <div className="mb-4 flex items-center gap-3">
            <span className="inline-flex size-10 items-center justify-center rounded-lg bg-zinc-100">
              <FileText className="size-5 text-zinc-600" />
            </span>
            <div className="min-w-0">
              <div className="truncate text-base font-semibold">{quote.code}</div>
              <div className="text-xs text-zinc-400">
                {quote.source === "agent" ? "AI 生成于" : "创建于"} {formatRelative(quote.created_at)}
              </div>
            </div>
          </div>
          <QuoteFields q={quote} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col lg:min-h-0">
          <RecordTabs
            value={tab}
            onValueChange={setTab}
            tabs={[
              {
                value: "bom",
                label: "物料清单",
                icon: List,
                // 草稿 + 负责人：可调数量和折扣（v3 §14）；其余只读
                content:
                  quote.status === "draft" && canEdit(quote.owner?.id) ? (
                    <QuoteAdjust key={adjustKey(quote)} q={quote} />
                  ) : (
                    <BomTable bom={quoteToBom(quote)} />
                  ),
              },
              {
                value: "timeline",
                label: "时间线",
                icon: Clock,
                content: <QuoteTimeline quoteId={quote.id} role={role} />,
              },
              {
                value: "approvals",
                label: `审批记录${quote.approvals.length ? ` ${quote.approvals.length}` : ""}`,
                icon: Stamp,
                content: <ApprovalRecords q={quote} />,
              },
            ]}
          />
        </div>
      </div>
    )
  }

  return (
    <PageFrame
      crumb={<Crumb parent="报价单" href="/quotes" icon={FileText} current={q?.code ?? "报价单"} />}
      actions={
        q ? (
          <>
            {approvalId ? (
              <FrameAction icon={Stamp} label="去审批" href={`/approvals?id=${encodeURIComponent(approvalId)}`} />
            ) : null}
            {canPrintQuote(q.status) ? (
              <FrameAction icon={Printer} label="打印报价单" href={`/quotes/${encodeURIComponent(q.id)}/print`} />
            ) : null}
            {canEdit(q.owner?.id) && canShareQuote(q.status, q.expired) ? <QuoteShareButton q={q} /> : null}
            {buttons}
            {q && q.status === "pending_approval" && canEdit(q.owner?.id) ? (
              <RemindButton targetType="quote" targetId={q.id} />
            ) : null}
          </>
        ) : null
      }
    >
      {body}
      {dialog}
    </PageFrame>
  )
}
