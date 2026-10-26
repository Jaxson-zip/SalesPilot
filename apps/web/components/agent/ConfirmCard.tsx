"use client"

import { CircleCheck, CircleX, ShieldCheck } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { ResumeDecision } from "@/types/api"

/** 写操作确认卡片（interrupt）：修改（传了 onModify 才显示）/ 取消 / 确认执行 */
export function ConfirmCard({
  title,
  rows,
  decision,
  busy,
  onDecide,
  onModify,
}: {
  title: string
  rows: [string, string][]
  decision?: ResumeDecision
  busy?: boolean
  onDecide: (decision: ResumeDecision) => void
  onModify?: () => void
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white text-sm shadow-sm">
      <div className="flex h-10 items-center gap-2 border-b border-zinc-100 px-3.5">
        <ShieldCheck className="text-ai size-4 shrink-0" />
        <span className="truncate font-medium">需要你确认：{title}</span>
      </div>
      {rows.length > 0 ? (
        <dl className="space-y-1.5 px-3.5 py-2.5">
          {rows.map(([k, v]) => (
            <div key={k} className="flex min-w-0">
              <dt className="w-16 shrink-0 text-zinc-500">{k}</dt>
              <dd className="min-w-0 break-words">{v}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      <div className="flex justify-end gap-2 px-3.5 pb-3">
        {decision === "approve" ? (
          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-700">
            <CircleCheck className="size-4" />
            已确认执行
          </span>
        ) : decision === "reject" ? (
          <span className="inline-flex items-center gap-1.5 text-xs text-zinc-500">
            <CircleX className="size-4" />
            已取消
          </span>
        ) : (
          <>
            {onModify ? (
              <Button variant="ghost" size="xs" className="h-7" onClick={onModify} disabled={busy}>
                修改
              </Button>
            ) : null}
            <Button variant="outline" size="xs" className="h-7" onClick={() => onDecide("reject")} disabled={busy}>
              取消
            </Button>
            <Button size="xs" className="h-7" onClick={() => onDecide("approve")} disabled={busy}>
              确认执行
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
