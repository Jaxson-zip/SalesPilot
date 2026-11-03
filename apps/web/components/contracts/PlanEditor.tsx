"use client"

import { Plus, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"

import { Alert } from "@/components/biz/Alert"
import { DatePicker, FormField, MoneyInput } from "@/components/biz/FormControls"
import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { useSavePaymentPlan } from "@/hooks/useContracts"
import { formatFen } from "@/lib/format"
import { changedFrom } from "@/lib/form-dirty"
import { yuanToFen } from "@/lib/money"
import { checkPlan, planNeedsReason, rowsTotal, toRows, type PlanRow } from "@/lib/payment-plan"
import type { PaymentPlanView } from "@/types/api"

const LOCK_HINT = {
  partial: (paid: number) => `已收 ${formatFen(paid)}：不能删除，金额不能低于已收`,
  invoiced: () => "已申请或已开票：不能删除，金额不能改",
}

/** 已收齐的期次：只显示，不能改（到账已经冲抵到这一期） */
function PaidRow({ row, index }: { row: PlanRow; index: number }) {
  return (
    <div
      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md bg-zinc-50 px-3 py-2 text-sm"
      role="group"
      aria-label={`第 ${index + 1} 期`}
    >
      <span className="font-medium">{row.name}</span>
      <span className="tabular-nums">{formatFen(yuanToFen(row.amount) ?? 0)}</span>
      <span className="text-zinc-500 tabular-nums">{row.due_date} 到期</span>
      <Tag color="green">已收齐，不能修改</Tag>
    </div>
  )
}

function EditRow({
  row,
  index,
  onChange,
  onRemove,
}: {
  row: PlanRow
  index: number
  onChange: (patch: Partial<PlanRow>) => void
  /** 不能删的期次不给删除按钮 */
  onRemove?: () => void
}) {
  const hint = row.lock === "partial" ? LOCK_HINT.partial(row.paid ?? 0) : row.lock ? LOCK_HINT.invoiced() : ""
  return (
    <div role="group" aria-label={`第 ${index + 1} 期`}>
      {/* 名称单独一行：侧栏窄时三栏挤在一行，名称只剩一个字 */}
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] items-center gap-2">
        <Input
          className="col-span-2"
          value={row.name}
          aria-label="期次名称"
          onChange={(e) => onChange({ name: e.target.value })}
        />
        {onRemove ? (
          <Button size="icon-sm" variant="ghost" aria-label={`删除第 ${index + 1} 期`} onClick={onRemove}>
            <Trash2 />
          </Button>
        ) : (
          <span className="size-7" />
        )}
        <MoneyInput value={row.amount} onChange={(v) => onChange({ amount: v })} />
        <DatePicker value={row.due_date} onChange={(v) => onChange({ due_date: v })} ariaLabel="到期日" />
      </div>
      {hint ? <p className="mt-1 text-xs text-zinc-500">{hint}</p> : null}
    </div>
  )
}

/** 调整回款计划：已收齐的期次锁定；合同已有回款、逾期或开票时要写原因（记进合同动态） */
export function PlanEditor({
  plan,
  onDone,
  onDirtyChange,
}: {
  plan: PaymentPlanView
  onDone: () => void
  /** 改过的计划没保存时，关闭侧栏要先确认 */
  onDirtyChange: (dirty: boolean) => void
}) {
  const [rows, setRows] = useState<PlanRow[]>(() => toRows(plan.items))
  const [reason, setReason] = useState("")
  const dirty = changedFrom(rows, toRows(plan.items)) || reason.trim() !== ""
  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange])
  const [error, setError] = useState<string>()
  const save = useSavePaymentPlan(plan.contract_id)
  const needReason = planNeedsReason(plan)
  const set = (i: number, patch: Partial<PlanRow>) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const diff = plan.amount - rowsTotal(rows)

  const submit = () => {
    const r = checkPlan(rows, plan.amount, reason, needReason)
    if (!r.ok) return setError(r.error)
    setError(undefined)
    save.mutate(r.value, { onSuccess: onDone })
  }

  return (
    <div className="space-y-3">
      {rows.map((r, i) =>
        r.lock === "paid" ? (
          <PaidRow key={i} row={r} index={i} />
        ) : (
          <EditRow
            key={i}
            row={r}
            index={i}
            onChange={(patch) => set(i, patch)}
            onRemove={r.lock || rows.length === 1 ? undefined : () => setRows((rs) => rs.filter((_, j) => j !== i))}
          />
        ),
      )}
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
      {needReason ? (
        <FormField label="调整原因" required htmlFor="plan-reason" hint="记进合同动态，连同原计划一起保留">
          <Textarea
            id="plan-reason"
            value={reason}
            maxLength={200}
            placeholder="例如：客户申请第二期延后一个月，已邮件确认"
            onChange={(e) => setReason(e.target.value)}
          />
        </FormField>
      ) : null}
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
