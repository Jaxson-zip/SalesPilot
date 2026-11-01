"use client"

import { Undo2 } from "lucide-react"
import { useState } from "react"

import { FormField } from "@/components/biz/FormControls"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
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
import { Textarea } from "@/components/ui/textarea"
import { usePayments, useReversePayment } from "@/hooks/useContracts"
import { formatFen, ownerName } from "@/lib/format"
import { canReversePayment, checkReverseReason, paymentDetail, paymentKind } from "@/lib/payments"
import { cn } from "@/lib/utils"
import type { PaymentRecord } from "@/types/api"

/** 冲正弹窗：写明原因后确认（不可逆：原记录保留，另记一笔负数） */
function ReverseDialog({
  contractId,
  target,
  onClose,
}: {
  contractId: string
  target: PaymentRecord | null
  onClose: () => void
}) {
  const [reason, setReason] = useState("")
  const [error, setError] = useState<string>()
  const reverse = useReversePayment(contractId)
  const close = () => {
    setReason("")
    setError(undefined)
    onClose()
  }
  const submit = () => {
    if (!target) return
    const err = checkReverseReason(reason)
    if (err) return setError(err)
    reverse.mutate({ pid: target.id, reason: reason.trim() }, { onSuccess: close })
  }
  return (
    <Dialog open={target !== null} onOpenChange={(o) => !o && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>冲正回款</DialogTitle>
          <DialogDescription>
            {target
              ? `冲正 ${target.received_on} 到账的 ${formatFen(target.amount)}：原记录保留，另记一笔负数，已回款和提成按新的回款比例重算。冲正后不能撤回。`
              : ""}
          </DialogDescription>
        </DialogHeader>
        <FormField label="冲正原因" required error={error} htmlFor="reverse-reason">
          <Textarea
            id="reverse-reason"
            value={reason}
            maxLength={200}
            placeholder="例如：金额录错，实际到账 ¥30,000"
            onChange={(e) => {
              setReason(e.target.value)
              setError(undefined)
            }}
          />
        </FormField>
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button variant="destructive" onClick={submit} disabled={reverse.isPending}>
            {reverse.isPending ? "提交中…" : "确认冲正"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** 回款记录：每笔到账的日期、流水号、备注、登记人；登记错了由本团队主管冲正 */
export function PaymentRecords({ contractId, manager }: { contractId: string; manager: boolean }) {
  const q = usePayments(contractId)
  const [target, setTarget] = useState<PaymentRecord | null>(null)
  if (q.isPending) return <Skeleton className="h-16 w-full" />
  if (q.isError) return <QueryError error={q.error} onRetry={() => void q.refetch()} feature="回款记录" />
  return (
    <section className="space-y-2" aria-label="回款记录">
      <h3 className="text-sm font-medium">回款记录</h3>
      {q.data.length === 0 ? (
        <p className="text-xs text-zinc-500">还没有登记过回款。</p>
      ) : (
        <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
          {q.data.map((p) => {
            const kind = paymentKind(p)
            return (
              <li key={p.id} className="flex items-start gap-3 px-3 py-2 text-sm">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "font-medium tabular-nums",
                        kind === "reversal" && "text-red-600",
                        kind === "reversed" && "text-zinc-400 line-through",
                      )}
                    >
                      {formatFen(p.amount)}
                    </span>
                    {kind === "reversal" ? <Tag color="red">冲正</Tag> : null}
                    {kind === "reversed" ? <Tag color="gray">已冲正</Tag> : null}
                  </div>
                  <div className="truncate text-xs text-zinc-500" title={paymentDetail(p)}>
                    {paymentDetail(p)}
                    {p.created_by ? ` · 登记人 ${ownerName(p.created_by)}` : ""}
                  </div>
                </div>
                {canReversePayment(p, manager) ? (
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() => setTarget(p)}
                    aria-label={`冲正 ${p.received_on} 的回款`}
                  >
                    <Undo2 /> 冲正
                  </Button>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
      <ReverseDialog contractId={contractId} target={target} onClose={() => setTarget(null)} />
    </section>
  )
}
