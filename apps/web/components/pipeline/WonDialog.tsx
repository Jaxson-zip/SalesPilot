"use client"

import { AlertTriangle } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { useOpportunity } from "@/hooks/useOpportunities"
import { stageConfirm } from "@/lib/confirm-texts"
import { formatFen } from "@/lib/format"
import { labelOf, QUOTE_STATUS_META } from "@/lib/labels"
import { quoteHref } from "@/lib/links"
import { aiPrefillHref } from "@/lib/thread-history"
import { cn } from "@/lib/utils"
import type { OpportunityItem, QuoteItem } from "@/types/api"

/** 能直接成交的报价：已审批 / 已发送客户（与后端 WIN_STATUSES 一致） */
const WINNABLE = new Set(["approved", "sent"])
const NONE = "none"

/**
 * 标记赢单：有可成交的报价时默认「按报价成交」——生成合同、回款计划和提成（与报价单「客户接受」相同）；
 * 没有报价时明确告知不会生成合同，避免「赢了单合同页却是空的」。
 */
export function WonDialog({
  opp,
  onCancel,
  onConfirm,
}: {
  opp: OpportunityItem | null
  onCancel: () => void
  onConfirm: (quote: QuoteItem | null) => void
}) {
  const detail = useOpportunity(opp?.id ?? null)
  const quotes = (detail.data?.quotes ?? []).filter((q) => WINNABLE.has(q.status))
  // 还没审批的报价（草稿 / 待审批）：直接打开它去提交，而不是丢到报价列表里找
  const unfinished = (detail.data?.quotes ?? []).find((q) => q.status === "draft" || q.status === "pending_approval")
  const [picked, setPicked] = useState<string | null>(null)
  const choice = picked ?? quotes[0]?.id ?? NONE
  const copy = stageConfirm(opp?.name ?? "")
  const close = () => {
    setPicked(null)
    onCancel()
  }
  return (
    <Dialog open={opp !== null} onOpenChange={(o) => !o && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{copy.title}</DialogTitle>
          <DialogDescription>{copy.description}</DialogDescription>
        </DialogHeader>
        {detail.isPending ? (
          <Skeleton className="h-16 w-full" />
        ) : quotes.length ? (
          <div role="radiogroup" aria-label="成交方式" className="space-y-1.5 text-sm">
            {[...quotes.map((q) => ({ id: q.id, q })), { id: NONE, q: null }].map(({ id, q }) => (
              <label
                key={id}
                className={cn(
                  "flex cursor-pointer items-start gap-2.5 rounded-lg border p-2.5",
                  choice === id ? "border-zinc-900" : "border-zinc-200 hover:bg-zinc-50",
                )}
              >
                <input
                  type="radio"
                  name="won-quote"
                  className="mt-1 accent-zinc-900"
                  checked={choice === id}
                  onChange={() => setPicked(id)}
                />
                {q ? (
                  <span className="min-w-0">
                    <span className="block">
                      按报价 {q.code} 成交 · <span className="tabular-nums">{formatFen(q.total_price)}</span>
                      <span className="ml-1.5 text-xs text-zinc-400">{labelOf(QUOTE_STATUS_META, q.status).label}</span>
                    </span>
                    <span className="block text-xs text-zinc-500">自动生成合同、回款计划和预估提成</span>
                  </span>
                ) : (
                  <span className="min-w-0">
                    <span className="block">只标记赢单</span>
                    <span className="block text-xs text-zinc-500">不生成合同，之后也不能再按报价成交</span>
                  </span>
                )}
              </label>
            ))}
          </div>
        ) : (
          <div className="flex items-start gap-1.5 rounded-md bg-amber-50 px-2.5 py-2 text-sm text-amber-800">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <span>
              这个商机还没有已审批或已发送的报价，标记赢单<b>不会生成合同和回款计划</b>，也不会计算提成。
              {unfinished ? (
                <>
                  报价{" "}
                  <Link href={quoteHref(unfinished.id)} className="underline">
                    {unfinished.code}
                  </Link>{" "}
                  还是「{labelOf(QUOTE_STATUS_META, unfinished.status).label}
                  」，审批通过后在报价单里点「客户接受」，会自动赢单并生成合同。
                </>
              ) : opp ? (
                <>
                  建议先
                  <Link
                    href={aiPrefillHref(`按${opp.customer.name}的需求给${opp.name}出方案和报价`, opp.id)}
                    className="underline"
                  >
                    让 AI 出方案和报价
                  </Link>
                  ，审批通过后在报价单里点「客户接受」，会自动赢单并生成合同。
                </>
              ) : null}
            </span>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button
            disabled={detail.isPending}
            onClick={() => {
              onConfirm(quotes.find((q) => q.id === choice) ?? null)
              setPicked(null)
            }}
          >
            {choice !== NONE ? "确认成交" : copy.confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
