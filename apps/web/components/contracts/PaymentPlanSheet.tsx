"use client"

import { CalendarClock, Plus, Printer, Trash2 } from "lucide-react"
import Link from "next/link"
import { Fragment, useState } from "react"

import { Alert } from "@/components/biz/Alert"
import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { DatePicker, MoneyInput } from "@/components/biz/FormControls"
import { FormSheet } from "@/components/biz/FormSheet"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { InvoiceDialog, type InvoiceTarget } from "@/components/contracts/InvoiceDialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useInvoice, usePaymentPlan, useSavePaymentPlan } from "@/hooks/useContracts"
import { formatFen, ownerName } from "@/lib/format"
import { INVOICE_STATUS_META, invoiceActions, invoiceDetail } from "@/lib/invoice"
import { PLAN_STATUS_META } from "@/lib/labels"
import { checkPlan, rowsTotal, toRows, type PlanRow } from "@/lib/payment-plan"
import type { ContractItem, PaymentPlanItem, PaymentPlanView } from "@/types/api"

/** 每期下面一行发票信息：状态 + 号码 / 备注；按角色给出操作（负责人申请，主管登记或作废） */
function InvoiceCell({
  item,
  who,
  onAct,
}: {
  item: PaymentPlanItem
  who: { owner: boolean; manager: boolean }
  onAct: (item: PaymentPlanItem, action: "request" | "issue" | "void") => void
}) {
  const m = INVOICE_STATUS_META[item.invoice_status ?? "none"]
  const detail = invoiceDetail(item)
  const unpaid = (item.invoiced_unpaid_days ?? 0) > 0
  const label = { request: "申请开票", issue: "登记开票", void: "作废" }
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
      <span className="text-zinc-500">发票</span>
      <Tag color={m.color}>{m.label}</Tag>
      {detail ? (
        <span className={unpaid ? "min-w-0 text-amber-700" : "min-w-0 text-zinc-500"} title={detail}>
          {detail}
        </span>
      ) : null}
      {invoiceActions(item, who).length > 0 ? (
        <div className="ml-auto flex gap-1">
          {invoiceActions(item, who).map((a) => (
            <Button
              key={a}
              size="xs"
              variant={a === "void" ? "ghost" : "outline"}
              aria-label={`${item.name}${label[a]}`}
              onClick={() => onAct(item, a)}
            >
              {label[a]}
            </Button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function PlanTable({
  plan,
  who,
  onInvoice,
}: {
  plan: PaymentPlanView
  who: { owner: boolean; manager: boolean }
  onInvoice: (item: PaymentPlanItem, action: "request" | "issue" | "void") => void
}) {
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
            <Fragment key={i.seq}>
              <tr>
                <td className="pt-2.5 pb-1 font-medium whitespace-nowrap">{i.name}</td>
                <td className="pt-2.5 pb-1 pl-2 text-right whitespace-nowrap tabular-nums">{formatFen(i.amount)}</td>
                <td className="pt-2.5 pb-1 pl-3 text-right whitespace-nowrap text-zinc-500 tabular-nums">
                  {formatFen(i.paid)}
                </td>
                <td className="pt-2.5 pb-1 pl-4 whitespace-nowrap tabular-nums">{i.due_date}</td>
                <td className="pt-2.5 pb-1 pl-2 whitespace-nowrap">
                  <Tag color={m.color}>{i.status === "overdue" ? `逾期 ${i.overdue_days} 天` : m.label}</Tag>
                </td>
              </tr>
              <tr className="border-b border-zinc-100">
                <td colSpan={5} className="pb-2.5">
                  <InvoiceCell item={i} who={who} onAct={onInvoice} />
                </td>
              </tr>
            </Fragment>
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

/** 回款计划（B9）：每期金额、到期日、已到账、是否逾期、开票状态；合同负责人可调整计划、申请开票，主管登记开票 */
export function PaymentPlanSheet({
  contract,
  editable,
  manager = false,
  onClose,
}: {
  contract: ContractItem | null
  editable: boolean
  /** 主管：登记已开票、作废 */
  manager?: boolean
  onClose: () => void
}) {
  const q = usePaymentPlan(contract?.id ?? null)
  const [editing, setEditing] = useState(false)
  const [invoiceOf, setInvoiceOf] = useState<InvoiceTarget | null>(null)
  const invoice = useInvoice(contract?.id ?? "")
  const { ask, dialog } = useConfirmAction()
  const onInvoice = (item: PaymentPlanItem, action: "request" | "issue" | "void") => {
    if (action !== "void") return setInvoiceOf({ item, action })
    ask({
      title: `作废「${item.name}」的发票？`,
      description:
        item.invoice_status === "issued"
          ? `发票 ${item.invoice_no ?? ""} 将标记为作废（需要在税务系统里另行红冲），这一期回到未开票。`
          : "撤回这一期的开票申请，回到未开票。",
      confirmLabel: "确认作废",
      destructive: true,
      onConfirm: () => invoice.mutate({ seq: item.seq, body: { action: "void" } }),
    })
  }
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
      ["已开票未回款", formatFen(plan.invoiced_unpaid_amount ?? 0), (plan.invoiced_unpaid_amount ?? 0) > 0],
    ]
    body = (
      <div className="space-y-4">
        <div className="text-sm text-zinc-600">
          {contract.customer?.name ?? "—"} · 负责人 {ownerName(contract.owner)}
        </div>
        <div className="grid grid-cols-2 gap-3">
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
            <PlanTable plan={plan} who={{ owner: editable, manager }} onInvoice={onInvoice} />
            <p className="text-xs text-zinc-500">
              回款按期次顺序冲抵：先收齐第一期，再算下一期。客户通常见票付款，已开票未回款的要重点跟进。
            </p>
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
      footer={
        contract ? (
          <Button variant="outline" asChild>
            <Link href={`/contracts/${encodeURIComponent(contract.id)}/print`}>
              <Printer />
              打印合同要素确认单
            </Link>
          </Button>
        ) : null
      }
    >
      {body}
      {contract ? (
        <InvoiceDialog
          key={invoiceOf ? `${invoiceOf.item.seq}-${invoiceOf.action}` : "none"}
          contractId={contract.id}
          target={invoiceOf}
          onClose={() => setInvoiceOf(null)}
        />
      ) : null}
      {dialog}
    </FormSheet>
  )
}
