"use client"

import { useState } from "react"
import { toast } from "sonner"

import { FormField, SimpleSelect } from "@/components/biz/FormControls"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useTransferCustomers } from "@/hooks/useCustomers"
import { useTeamUsers } from "@/hooks/useUsers"
import { transferConfirm } from "@/lib/confirm-texts"
import { errorMessage } from "@/lib/errors"
import type { Customer } from "@/types/api"

/**
 * 转移负责人（仅主管，v3 §16）：选择本团队成员 → 对话框里写明后果 →「确认转移」后执行，成功后清空选择。
 */
export function TransferDialog({
  customers,
  open,
  onOpenChange,
  onDone,
}: {
  customers: Customer[]
  open: boolean
  onOpenChange: (o: boolean) => void
  onDone: () => void
}) {
  const [to, setTo] = useState("")
  const users = useTeamUsers(open)
  const transfer = useTransferCustomers()
  const options = (users.data?.items ?? []).map((u) => ({ value: u.id, label: u.name }))
  const target = options.find((o) => o.value === to) ?? null
  const copy = transferConfirm(customers.length, target?.label ?? null)

  const close = () => {
    setTo("")
    onOpenChange(false)
  }
  const confirm = () => {
    if (!target) return
    transfer.mutate(
      { customer_ids: customers.map((c) => c.id), to_user_id: target.value },
      {
        onSuccess: (r) => {
          toast.success(`已转移 ${r?.transferred ?? customers.length} 个客户`, {
            description: `新负责人：${target.label}`,
          })
          close()
          onDone()
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{copy.title}</DialogTitle>
          <DialogDescription>{copy.description}</DialogDescription>
        </DialogHeader>
        <FormField
          label="新负责人"
          required
          htmlFor="transfer-to"
          error={users.isError ? errorMessage(users.error) : undefined}
        >
          <SimpleSelect
            id="transfer-to"
            value={to}
            onChange={setTo}
            options={options}
            placeholder={users.isPending ? "加载团队成员…" : "选择本团队成员"}
            ariaLabel="新负责人"
          />
        </FormField>
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button onClick={confirm} disabled={!target || transfer.isPending}>
            {transfer.isPending ? "转移中…" : copy.confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
