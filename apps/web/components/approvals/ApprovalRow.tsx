"use client"

import { FileText, Lightbulb, Receipt } from "lucide-react"
import Link from "next/link"
import { useEffect, useRef } from "react"

import { AttachmentPill } from "@/components/biz/Attachments"
import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { formatFen, formatPercent, formatRelative, ownerName } from "@/lib/format"
import { APPROVAL_STATUS_META, APPROVAL_TARGET_LABEL, labelOf } from "@/lib/labels"
import { subjectHref } from "@/lib/links"
import { cn } from "@/lib/utils"
import type { ApprovalItem } from "@/types/api"

/** 金额下面那一行：报销看超标多少，报价看毛利 */
function KeyFigure({ a }: { a: ApprovalItem }) {
  const t = a.target
  if (a.target_type === "expense" && t.over_amount)
    return <div className="text-sm font-medium text-red-600 tabular-nums">超标 {formatFen(t.over_amount)}</div>
  if (a.target_type === "quote" && typeof t.margin_rate === "number")
    return <div className="text-sm font-medium text-amber-600 tabular-nums">毛利 {formatPercent(t.margin_rate)}</div>
  return null
}

/**
 * 一条审批：主管先看「多少钱、超了多少」，所以金额放右上角大字，超标 / 毛利紧跟其下；
 * 左边是事由（类型 · 客户）、申请人与时间、为什么要审批、票据；AI 建议放最后、最多两行。
 */
export function ApprovalRow({
  a,
  busy,
  onApprove,
  onReject,
  selected,
  onSelectedChange,
  focused,
}: {
  a: ApprovalItem
  busy?: boolean
  onApprove: () => void
  onReject: () => void
  /** 传了就显示勾选框（待处理列表批量操作） */
  selected?: boolean
  onSelectedChange?: (v: boolean) => void
  /** 从通知点进来的那一条：滚到可见处并高亮 */
  focused?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (focused) ref.current?.scrollIntoView({ block: "center" })
  }, [focused])
  const Icon = a.target_type === "quote" ? FileText : Receipt
  const status = labelOf(APPROVAL_STATUS_META, a.status)
  const t = a.target
  const occurred = t.occurred_on ? `${t.occurred_on.slice(5)} 发生` : null
  const title = <span className="font-medium break-words">{t.title || t.code}</span>
  const actions =
    a.status === "pending" ? (
      <>
        <Button variant="outline" size="sm" disabled={busy} onClick={onReject}>
          驳回
        </Button>
        <Button size="sm" disabled={busy} onClick={onApprove}>
          通过
        </Button>
      </>
    ) : (
      <Tag color={status.color}>{status.label}</Tag>
    )
  return (
    <div
      ref={ref}
      data-focused={focused || undefined}
      className={cn(
        "flex gap-3 border-b border-zinc-100 px-4 py-4 sm:px-5",
        selected ? "bg-zinc-50" : "hover:bg-zinc-50/60",
        focused && "bg-amber-50/70 ring-1 ring-amber-300 ring-inset",
      )}
    >
      {onSelectedChange ? (
        <Checkbox
          aria-label={`选择 ${t.code}`}
          checked={Boolean(selected)}
          onCheckedChange={(v) => onSelectedChange(v === true)}
          className="mt-1 shrink-0"
        />
      ) : null}
      <span className="hidden size-9 shrink-0 items-center justify-center rounded-lg bg-zinc-100 sm:inline-flex">
        <Icon className="size-4 text-zinc-600" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 items-center gap-2">
              <Tag>{APPROVAL_TARGET_LABEL[a.target_type]}</Tag>
              {subjectHref(a.target_type, t.id) ? (
                <Link href={subjectHref(a.target_type, t.id) ?? ""} className="min-w-0 hover:underline">
                  {title}
                </Link>
              ) : (
                title
              )}
            </div>
            <div className="mt-1 text-xs text-zinc-500">
              {[t.code, ownerName(t.owner), occurred, `${formatRelative(a.created_at)}提交`]
                .filter(Boolean)
                .join(" · ")}
            </div>
          </div>
          <div className="shrink-0 text-right sm:hidden">
            <div className="text-lg leading-6 font-semibold tabular-nums">{formatFen(t.amount)}</div>
            <KeyFigure a={a} />
          </div>
        </div>

        <div className="mt-2 text-zinc-700">{a.reason}</div>

        {a.attachments.length ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {a.attachments.map((f) => (
              <AttachmentPill key={f.id} a={f} />
            ))}
          </div>
        ) : null}

        {a.ai_suggestion ? (
          <div className="mt-2 flex items-start gap-1.5 text-xs text-zinc-500">
            <Lightbulb className="mt-px size-3.5 shrink-0 text-amber-500" />
            <span className="line-clamp-2" title={a.ai_suggestion}>
              审批建议：{a.ai_suggestion}
            </span>
          </div>
        ) : null}

        {a.comment ? <div className="mt-2 text-xs text-zinc-500">审批意见：{a.comment}</div> : null}
        {/* 手机：按钮放最下面一行 */}
        <div className="mt-3 flex items-center justify-end gap-2 sm:hidden">{actions}</div>
      </div>
      {/* 桌面：金额、超标、按钮竖排在右侧一列 */}
      <div className="hidden w-40 shrink-0 flex-col items-end gap-0.5 text-right sm:flex">
        <div className="text-lg leading-6 font-semibold tabular-nums">{formatFen(t.amount)}</div>
        <KeyFigure a={a} />
        <div className="mt-auto flex gap-2 pt-3">{actions}</div>
      </div>
    </div>
  )
}
