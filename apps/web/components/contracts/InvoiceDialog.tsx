"use client"

import { useState } from "react"

import { DatePicker, FormField, SimpleSelect } from "@/components/biz/FormControls"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { useInvoice } from "@/hooks/useContracts"
import { formatFen, localDate } from "@/lib/format"
import { INVOICE_TYPE_OPTIONS } from "@/lib/invoice"
import type { InvoiceType, PaymentPlanItem } from "@/types/api"

export interface InvoiceTarget {
  item: PaymentPlanItem
  /** request 负责人申请开票；issue 主管登记已开票 */
  action: "request" | "issue"
}

/** 申请开票（选专票 / 普票，备注抬头税号）或登记已开票（发票号码、开票日期） */
export function InvoiceDialog({
  contractId,
  target,
  onClose,
}: {
  contractId: string
  target: InvoiceTarget | null
  onClose: () => void
}) {
  const item = target?.item
  const issuing = target?.action === "issue"
  const [type, setType] = useState<InvoiceType>(item?.invoice_type ?? "special")
  const [no, setNo] = useState("")
  const [date, setDate] = useState(localDate())
  const [note, setNote] = useState("")
  const [error, setError] = useState<string>()
  const invoice = useInvoice(contractId)

  const submit = () => {
    if (!item || !target) return
    if (issuing && !no.trim()) return setError("请填写发票号码")
    const body = issuing
      ? { action: "issue" as const, invoice_type: type, invoice_no: no.trim(), invoiced_on: date }
      : { action: "request" as const, invoice_type: type, note: note.trim() || undefined }
    invoice.mutate({ seq: item.seq, body }, { onSuccess: onClose })
  }

  return (
    <Dialog open={target !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{issuing ? "登记已开票" : "申请开票"}</DialogTitle>
          <DialogDescription>
            {item ? `${item.name} · ${formatFen(item.amount)}` : ""}
            {issuing ? "；登记后负责人会收到通知" : "；提交后本团队主管会收到通知"}
          </DialogDescription>
        </DialogHeader>
        <FormField label="发票类型" htmlFor="invoice-type">
          <SimpleSelect id="invoice-type" value={type} onChange={setType} options={INVOICE_TYPE_OPTIONS} />
        </FormField>
        {issuing ? (
          <>
            <FormField label="发票号码" required error={error} htmlFor="invoice-no">
              <Input
                id="invoice-no"
                value={no}
                maxLength={50}
                aria-invalid={Boolean(error)}
                onChange={(e) => {
                  setNo(e.target.value)
                  setError(undefined)
                }}
              />
            </FormField>
            <FormField label="开票日期">
              <DatePicker value={date} onChange={setDate} ariaLabel="开票日期" />
            </FormField>
          </>
        ) : (
          <FormField label="备注" hint="如开票抬头、税号、寄送地址（选填）" htmlFor="invoice-note">
            <Input id="invoice-note" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
          </FormField>
        )}
        {item?.invoice_note && issuing ? <p className="text-xs text-zinc-500">申请备注：{item.invoice_note}</p> : null}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={submit} disabled={invoice.isPending}>
            {invoice.isPending ? "提交中…" : issuing ? "登记" : "提交申请"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
