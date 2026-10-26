"use client"

import { Boxes, Building2, CircleDot, Coins, Layers, Percent, Stamp, Target, User, Wallet } from "lucide-react"
import Link from "next/link"

import { Alert } from "@/components/biz/Alert"
import { Chip } from "@/components/biz/Chip"
import { EmptyState } from "@/components/biz/EmptyState"
import { FieldRow } from "@/components/biz/FieldRow"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { Skeleton } from "@/components/ui/skeleton"
import { useActivities } from "@/hooks/useDashboard"
import { formatFen, formatPercent, formatRelative } from "@/lib/format"
import { activityActionLabel, APPROVAL_STATUS_META, labelOf, QUOTE_STATUS_META } from "@/lib/labels"
import { defaultScope } from "@/lib/views"
import type { QuoteDetail, Role } from "@/types/api"
import { PackName } from "@/components/biz/PackName"

/** 左侧字段面板顶部的规则提示：阈值由 core 判断，这里只展示结果 */
function RuleAlert({ q }: { q: QuoteDetail }) {
  const pending = q.approvals.find((a) => a.status === "pending")
  const last = q.approvals[q.approvals.length - 1]
  if (pending)
    return (
      <Alert tone="warn" title="已触发审批规则，等待主管审批">
        {pending.reason}
      </Alert>
    )
  if (q.status === "draft" && last?.status === "rejected")
    return (
      <Alert tone="warn" title="主管已驳回，退回草稿">
        {last.comment || last.reason}
      </Alert>
    )
  if (q.status === "draft")
    return (
      <Alert tone="info" title="提交后按业务规则自动判断">
        毛利达标自动通过；低于底线或折扣超权限时进入主管审批
      </Alert>
    )
  if (q.status === "accepted")
    return (
      <Alert tone="ok" title="客户已接受">
        已生成合同
        {q.contract_id ? (
          <Link href="/contracts" className="ml-1 underline">
            查看合同
          </Link>
        ) : null}
      </Alert>
    )
  return null
}

export function QuoteFields({ q }: { q: QuoteDetail }) {
  const status = labelOf(QUOTE_STATUS_META, q.status)
  return (
    <>
      <FieldRow icon={CircleDot} label="状态">
        <Tag color={status.color}>{status.label}</Tag>
      </FieldRow>
      <FieldRow icon={Building2} label="客户">
        {q.customer ? (
          <Link href={`/customers/${q.customer.id}`} className="inline-flex max-w-full">
            <Chip name={q.customer.name} logo={q.customer.name.slice(0, 1)} />
          </Link>
        ) : (
          "—"
        )}
      </FieldRow>
      <FieldRow icon={Target} label="商机">
        {q.opportunity?.name ?? "—"}
      </FieldRow>
      <FieldRow icon={Boxes} label="行业包">
        <PackName id={q.pack} />
      </FieldRow>
      <FieldRow icon={Layers} label="方案档位">
        {q.tier_name || q.tier || "—"}
      </FieldRow>
      <FieldRow icon={Coins} label="报价合计">
        <b className="tabular-nums">{formatFen(q.total_price)}</b>
      </FieldRow>
      <FieldRow icon={Percent} label="毛利率">
        <span className="tabular-nums">{formatPercent(q.margin_rate)}</span>
      </FieldRow>
      <FieldRow icon={Wallet} label="预估提成">
        <span className="tabular-nums">{formatFen(q.estimated_commission)}</span>
      </FieldRow>
      <FieldRow icon={User} label="负责人">
        <Chip name={q.owner.name} />
      </FieldRow>
      <div className="mt-4">
        <RuleAlert q={q} />
      </div>
    </>
  )
}

export function ApprovalRecords({ q }: { q: QuoteDetail }) {
  if (q.approvals.length === 0)
    return <EmptyState icon={Stamp} title="没有审批记录" description="毛利达标的报价提交后自动通过，不产生审批。" />
  return (
    <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
      {q.approvals.map((a) => {
        const m = labelOf(APPROVAL_STATUS_META, a.status)
        return (
          <div key={a.id} className="space-y-1.5 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <Tag color={m.color}>{m.label}</Tag>
              {a.approver ? <Chip name={a.approver.name} /> : <span className="text-zinc-400">待主管处理</span>}
              <span className="flex-1" />
              <span className="text-xs text-zinc-400">{a.decided_at ? formatRelative(a.decided_at) : ""}</span>
            </div>
            <div className="text-zinc-700">触发原因：{a.reason}</div>
            {a.comment ? <div className="text-zinc-500">审批意见：{a.comment}</div> : null}
          </div>
        )
      })}
    </div>
  )
}

export function QuoteTimeline({ quoteId, role }: { quoteId: string; role: Role }) {
  const query = useActivities({ view: defaultScope(role), subject_type: "quote", subject_id: quoteId, limit: 50 })
  if (query.isPending) return <Skeleton className="h-24 w-full" />
  if (query.isError) return <QueryError error={query.error} onRetry={() => void query.refetch()} feature="动态" />
  if (query.data.length === 0) return <EmptyState title="暂无动态" />
  return (
    <div className="space-y-3">
      {query.data.map((a) => (
        <div key={a.id} className="flex items-start gap-2.5">
          <Chip name={a.actor?.name ?? "AI"} />
          <div className="min-w-0 flex-1">
            <span className="text-zinc-500">{activityActionLabel(a.action, a.subject_type)}</span>
            {a.content ? <div className="mt-0.5 break-words text-zinc-700">{a.content}</div> : null}
          </div>
          <span className="shrink-0 text-xs text-zinc-400">{formatRelative(a.created_at)}</span>
        </div>
      ))}
    </div>
  )
}
