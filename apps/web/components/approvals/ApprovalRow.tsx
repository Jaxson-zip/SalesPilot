"use client"

import { FileText, Receipt, Sparkles, TriangleAlert } from "lucide-react"
import Link from "next/link"

import { AttachmentPill } from "@/components/biz/Attachments"
import { Chip } from "@/components/biz/Chip"
import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { formatFen, formatRelative, ownerName } from "@/lib/format"
import { APPROVAL_STATUS_META, APPROVAL_TARGET_LABEL, labelOf } from "@/lib/labels"
import type { ApprovalItem } from "@/types/api"

/** ApprovalItem：类型、单据、金额、触发原因、附件、AI 建议、通过 / 驳回 */
export function ApprovalRow({
  a,
  busy,
  onApprove,
  onReject,
}: {
  a: ApprovalItem
  busy?: boolean
  onApprove: () => void
  onReject: () => void
}) {
  const Icon = a.target_type === "quote" ? FileText : Receipt
  const status = labelOf(APPROVAL_STATUS_META, a.status)
  const title = (
    <span className="min-w-0 truncate font-medium">
      {a.target.code}
      {a.target.title ? ` · ${a.target.title}` : ""}
    </span>
  )
  return (
    <div className="flex flex-wrap gap-3 border-b border-zinc-100 px-4 py-4 hover:bg-zinc-50/60 sm:flex-nowrap sm:px-5">
      <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-zinc-100">
        <Icon className="size-4 text-zinc-600" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <Tag>{APPROVAL_TARGET_LABEL[a.target_type]}</Tag>
          {a.target_type === "quote" ? (
            <Link href={`/quotes/${a.target.id}`} className="min-w-0 truncate hover:underline">
              {title}
            </Link>
          ) : (
            title
          )}
          <span className="shrink-0 text-zinc-500 tabular-nums">{formatFen(a.target.amount)}</span>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-zinc-500">
          <Chip name={ownerName(a.target.owner)} />
          <span>{formatRelative(a.created_at)} 提交 ·</span>
          <TriangleAlert className="size-3.5 text-amber-500" />
          <span className="text-zinc-700">{a.reason}</span>
        </div>
        {a.attachments.length ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {a.attachments.map((f) => (
              <AttachmentPill key={f.id} a={f} />
            ))}
          </div>
        ) : null}
        {a.ai_suggestion ? (
          <div className="mt-2 inline-flex items-start gap-1.5 text-violet-700">
            <Sparkles className="mt-0.5 size-3.5 shrink-0" />
            <span>AI 建议：{a.ai_suggestion}</span>
          </div>
        ) : null}
      </div>
      <div className="flex w-full shrink-0 items-start justify-end gap-2 sm:w-auto">
        {a.status === "pending" ? (
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
        )}
      </div>
    </div>
  )
}
