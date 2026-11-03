"use client"

import { CalendarClock, Printer } from "lucide-react"
import Link from "next/link"
import { Fragment, useState } from "react"

import { Alert } from "@/components/biz/Alert"
import { FormSheet } from "@/components/biz/FormSheet"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { InvoiceDialog, type InvoiceTarget } from "@/components/contracts/InvoiceDialog"
import { InvoiceHistory } from "@/components/contracts/InvoiceHistory"
import { PaymentRecords } from "@/components/contracts/PaymentRecords"
import { PlanEditor } from "@/components/contracts/PlanEditor"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { usePaymentPlan } from "@/hooks/useContracts"
import { formatFen, ownerName } from "@/lib/format"
import { INVOICE_STATUS_META, invoiceActions, invoiceDetail } from "@/lib/invoice"
import { PLAN_STATUS_META } from "@/lib/labels"
import { customerHref, quoteHref } from "@/lib/links"
import { planFullyPaid } from "@/lib/payment-plan"
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
          <th className="py-2 text-right font-normal" title="合同已回款按期次顺序冲抵到各期的金额">
            已冲抵
          </th>
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
  const [dirty, setDirty] = useState(false)
  const [invoiceOf, setInvoiceOf] = useState<InvoiceTarget | null>(null)
  // 作废也走弹框：要写原因（开票历史里留底），弹框本身就是二次确认
  const onInvoice = (item: PaymentPlanItem, action: "request" | "issue" | "void") => setInvoiceOf({ item, action })
  const close = () => {
    setEditing(false)
    setDirty(false)
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
          {contract.customer ? (
            <Link href={customerHref(contract.customer.id)} className="text-zinc-900 hover:underline">
              {contract.customer.name}
            </Link>
          ) : (
            "—"
          )}
          {contract.quote ? (
            <>
              {" · 报价 "}
              <Link href={quoteHref(contract.quote.id)} className="text-zinc-900 hover:underline">
                {contract.quote.code}
              </Link>
            </>
          ) : null}
          {` · 负责人 ${ownerName(contract.owner)}`}
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
          <PlanEditor
            plan={plan}
            onDirtyChange={setDirty}
            onDone={() => {
              setEditing(false)
              setDirty(false)
            }}
          />
        ) : (
          <>
            <PlanTable plan={plan} who={{ owner: editable, manager }} onInvoice={onInvoice} />
            <p className="text-xs text-zinc-500">
              「已冲抵」是系统把已回款按期次顺序分配的结果：先收齐第一期，再算下一期，不代表客户付款时指定的期次；每笔实际到账见下方回款记录。客户通常见票付款，已开票未回款的要重点跟进。
            </p>
            {editable && !planFullyPaid(plan) ? (
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                <CalendarClock /> 调整计划
              </Button>
            ) : null}
            <PaymentRecords contractId={contract.id} manager={manager} />
            <InvoiceHistory events={plan.invoice_events ?? []} />
          </>
        )}
      </div>
    )
  }

  return (
    <FormSheet
      open={contract !== null}
      onOpenChange={(o) => !o && close()}
      dirty={editing && dirty}
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
    </FormSheet>
  )
}
