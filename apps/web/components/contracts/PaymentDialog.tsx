"use client"

import { useEffect, useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { DatePicker, FormField, MoneyInput } from "@/components/biz/FormControls"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useRegisterPayment } from "@/hooks/useContracts"
import { paymentConfirm } from "@/lib/confirm-texts"
import { checkPayment, newRequestKey, suggestedPayment, unpaidOf } from "@/lib/contract"
import { formatFen, localDate } from "@/lib/format"
import type { ContractItem } from "@/types/api"

/** 登记回款（仅主管 / 管理员）；提成确认金额由 core 按回款比例计算 */
export function PaymentDialog({ contract, onClose }: { contract: ContractItem | null; onClose: () => void }) {
  const [amount, setAmount] = useState("")
  // 对账信息：到账日期（默认今天）、银行流水号、备注
  const [receivedOn, setReceivedOn] = useState(localDate())
  const [refNo, setRefNo] = useState("")
  const [note, setNote] = useState("")
  const [error, setError] = useState<string>()
  // 这一次登记的请求键：网络出错后重新提交沿用，后端识别为同一笔
  const [requestKey, setRequestKey] = useState(newRequestKey)
  const pay = useRegisterPayment()
  const { ask, dialog } = useConfirmAction()
  // 打开时预填下一期还没收的金额，客户付的不是整期时再改
  useEffect(() => {
    if (contract) {
      setAmount(suggestedPayment(contract))
      setRequestKey(newRequestKey())
    }
  }, [contract])
  const close = () => {
    setAmount("")
    setReceivedOn(localDate())
    setRefNo("")
    setNote("")
    setError(undefined)
    onClose()
  }
  const submit = () => {
    if (!contract) return
    const r = checkPayment(amount, contract)
    if (!r.ok) return setError(r.error)
    const { id, code } = contract
    // 回款登记后会确认提成、不能修改（录错只能冲正）：先二次确认
    ask({
      ...paymentConfirm(formatFen(r.amount), code),
      onConfirm: () =>
        pay.mutate(
          {
            id,
            amount: r.amount,
            received_on: receivedOn || null,
            reference_no: refNo.trim() || null,
            note: note.trim() || null,
            idempotency_key: requestKey,
          },
          { onSuccess: close },
        ),
    })
  }
  return (
    <Dialog open={contract !== null} onOpenChange={(o) => !o && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>登记回款</DialogTitle>
          <DialogDescription>
            {contract
              ? `${contract.code} · 合同金额 ${formatFen(contract.amount)}，未回款 ${formatFen(unpaidOf(contract))}`
              : ""}
          </DialogDescription>
        </DialogHeader>
        <FormField
          label="本次回款金额"
          required
          error={error}
          hint={
            contract?.next_payment
              ? `已按下一期「${contract.next_payment.name}」未收金额预填，可修改；提成按回款比例自动确认`
              : "提成按回款比例自动确认"
          }
          htmlFor="pay-amount"
        >
          <MoneyInput
            id="pay-amount"
            value={amount}
            invalid={Boolean(error)}
            onChange={(v) => {
              setAmount(v)
              setError(undefined)
            }}
          />
        </FormField>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="到账日期" required htmlFor="pay-date">
            <DatePicker value={receivedOn} onChange={setReceivedOn} max={localDate()} ariaLabel="到账日期" />
          </FormField>
          <FormField label="银行流水号 / 交易单号" htmlFor="pay-ref">
            <Input id="pay-ref" value={refNo} maxLength={64} onChange={(e) => setRefNo(e.target.value)} />
          </FormField>
        </div>
        <FormField label="备注" htmlFor="pay-note" hint="例如付款方户名、对应第几期">
          <Input id="pay-note" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
        </FormField>
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button onClick={submit} disabled={pay.isPending || !amount}>
            {pay.isPending ? "提交中…" : "下一步"}
          </Button>
        </DialogFooter>
      </DialogContent>
      {dialog}
    </Dialog>
  )
}
