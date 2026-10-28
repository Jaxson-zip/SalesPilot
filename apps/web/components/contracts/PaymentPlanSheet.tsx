"use client"

import { CalendarClock, Plus, Trash2 } from "lucide-react"
import { useState } from "react"

import { Alert } from "@/components/biz/Alert"
import { DatePicker, MoneyInput } from "@/components/biz/FormControls"
import { FormSheet } from "@/components/biz/FormSheet"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { usePaymentPlan, useSavePaymentPlan } from "@/hooks/useContracts"
import { formatFen } from "@/lib/format"
import { PLAN_STATUS_META } from "@/lib/labels"
import { checkPlan, rowsTotal, toRows, type PlanRow } from "@/lib/payment-plan"
import type { ContractItem, PaymentPlanView } from "@/types/api"

function PlanTable({ plan }: { plan: PaymentPlanView }) {
  return (
    <table className="w-full text-left" aria-label="回款计划">
      <thead className="text-xs text-zinc-500">
        <tr className="border-b border-zinc-200">
          <th className="py-2 font-normal">期次</th>
          <th className="py-2 text-right font-normal">金额</th>
          <th className="py-2 text-right font-normal">已到账</th>
          <th className="py-2 pl-4 font-normal">到期日</th>
          <th className="py-2 font-normal">状态</th>
        </tr>
      </thead>
      <tbody>
        {plan.items.map((i) => {
          const m = PLAN_STATUS_META[i.status]
          return (
            <tr key={i.seq} className="border-b border-zinc-100">
              <td className="py-2.5 font-medium">{i.name}</td>
              <td className="py-2.5 text-right tabular-nums">{formatFen(i.amount)}</td>
              <td className="py-2.5 text-right text-zinc-500 tabular-nums">{formatFen(i.paid)}</td>
              <td className="py-2.5 pl-4 tabular-nums">{i.due_date}</td>
              <td className="py-2.5">
                <Tag color={m.color}>{i.status === "overdue" ? `逾期 ${i.overdue_days} 天` : m.label}</Tag>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function PlanEditor({ plan, onDone }: { plan: PaymentPlanView; onDone: () => void }) {
  const [rows, setRows] = useState<PlanRow[]>(() => toRows(plan.items))
  const [error, setError] = useState<string>()
  const save = useSavePaymentPlan(plan.contract_id)
  const set = (i: number, patch: Partial<PlanRow>) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const diff = plan.amount - rowsTotal(rows)

  const submit = () => {
    const r = checkPlan(rows, plan.amount)
    if (!r.ok) return setError(r.error)
    setError(undefined)
    save.mutate(r.value, { onSuccess: onDone })
  }

  return (
    <div className="space-y-3">
      {rows.map((r, i) => (
        <div
          key={i}
          className="grid grid-cols-[1fr_8.5rem_9.5rem_auto] items-center gap-2"
          role="group"
          aria-label={`第 ${i + 1} 期`}
        >
          <Input value={r.name} aria-label="期次名称" onChange={(e) => set(i, { name: e.target.value })} />
          <MoneyInput value={r.amount} onChange={(v) => set(i, { amount: v })} />
          <DatePicker value={r.due_date} onChange={(v) => set(i, { due_date: v })} ariaLabel="到期日" />
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label={`删除第 ${i + 1} 期`}
            disabled={rows.length === 1}
            onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}
          >
            <Trash2 />
          </Button>
        </div>
      ))}
      <div className="flex items-center justify-between">
        <Button
          size="sm"
          variant="outline"
          onClick={() => setRows((rs) => [...rs, { name: `第 ${rs.length + 1} 期`, amount: "", due_date: "" }])}
        >
          <Plus /> 加一期
        </Button>
        <span className={diff === 0 ? "text-zinc-500" : "text-amber-700"}>
          {diff === 0 ? "合计等于合同金额" : diff > 0 ? `还差 ${formatFen(diff)}` : `多了 ${formatFen(-diff)}`}
        </span>
      </div>
      {error ? (
        <Alert tone="warn" title="还不能保存">
          {error}
        </Alert>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onDone}>
          取消
        </Button>
        <Button onClick={submit} disabled={save.isPending}>
          {save.isPending ? "保存中…" : "保存计划"}
        </Button>
      </div>
    </div>
  )
}

/** 回款计划（B9）：每期金额、到期日、已到账、是否逾期；合同负责人可调整 */
export function PaymentPlanSheet({
  contract,
  editable,
  onClose,
}: {
  contract: ContractItem | null
  editable: boolean
  onClose: () => void
}) {
  const q = usePaymentPlan(contract?.id ?? null)
  const [editing, setEditing] = useState(false)
  const close = () => {
    setEditing(false)
    onClose()
  }

  let body
  if (!contract || q.isPending) body = <Skeleton className="h-40 w-full" />
  else if (q.isError) body = <QueryError error={q.error} onRetry={() => void q.refetch()} feature="回款计划" />
  else {
    const plan = q.data
    const stats: [string, string, boolean][] = [
      ["合同金额", formatFen(plan.amount), false],
      ["已回款", formatFen(plan.paid_amount), false],
      ["逾期未收", formatFen(plan.overdue_amount), plan.overdue_amount > 0],
    ]
    body = (
      <div className="space-y-4">
        <div className="grid grid-cols-3 gap-3">
          {stats.map(([k, v, alert]) => (
            <div key={k} className="rounded-lg border border-zinc-200 px-3 py-2">
              <div className="text-xs text-zinc-500">{k}</div>
              <div className={alert ? "font-semibold text-red-600 tabular-nums" : "font-semibold tabular-nums"}>
                {v}
              </div>
            </div>
          ))}
        </div>
        {plan.overdue_amount > 0 ? (
          <Alert tone="warn" title="有逾期未收的款项">
            逾期超过 30 天须每周跟进；超过 90 天暂停该客户新报价的审批（{plan.rule_ref}）。
          </Alert>
        ) : null}
        {editing ? (
          <PlanEditor plan={plan} onDone={() => setEditing(false)} />
        ) : (
          <>
            <PlanTable plan={plan} />
            <p className="text-xs text-zinc-500">回款按期次顺序冲抵：先收齐第一期，再算下一期。</p>
            {editable ? (
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                <CalendarClock /> 调整计划
              </Button>
            ) : null}
          </>
        )}
      </div>
    )
  }

  return (
    <FormSheet
      open={contract !== null}
      onOpenChange={(o) => !o && close()}
      title={`回款计划 · ${contract?.code ?? ""}`}
    >
      {body}
    </FormSheet>
  )
}
