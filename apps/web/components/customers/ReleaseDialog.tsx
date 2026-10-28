"use client"

import { useState } from "react"

import { QuickChips } from "@/components/biz/QuickChips"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { useReleaseCustomer } from "@/hooks/useCustomers"
import { POOL_RELEASE_REASONS } from "@/lib/customer"
import { pickReason } from "@/lib/templates"
import type { CustomerDetail } from "@/types/api"

/** 退回公海（B5）：写明原因；有进行中商机时后端拒绝（42201），提示由 mutation 负责 */
export function ReleaseDialog({
  customer,
  open,
  onOpenChange,
}: {
  customer: CustomerDetail
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [reason, setReason] = useState("")
  const release = useReleaseCustomer(customer.id)
  const close = () => {
    setReason("")
    onOpenChange(false)
  }
  return (
    <Dialog open={open} onOpenChange={(o) => !o && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>退回公海</DialogTitle>
          <DialogDescription>
            「{customer.name}」退回后没有负责人，本团队的销售可以领取，主管也可以直接分配。联系人和跟进记录会保留。
          </DialogDescription>
        </DialogHeader>
        <QuickChips
          label="常见原因"
          items={POOL_RELEASE_REASONS.map((r) => ({ key: r, label: r }))}
          onPick={(r) => setReason((cur) => pickReason(cur, r))}
        />
        <Textarea
          autoFocus
          rows={3}
          value={reason}
          maxLength={200}
          aria-label="退回原因"
          placeholder="选一个常见原因，再补充具体情况"
          onChange={(e) => setReason(e.target.value)}
        />
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button
            disabled={!reason.trim() || release.isPending}
            onClick={() => release.mutate({ reason: reason.trim() }, { onSuccess: close })}
          >
            确认退回
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
