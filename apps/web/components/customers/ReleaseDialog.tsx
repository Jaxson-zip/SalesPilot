"use client"

import { useState } from "react"

import { Alert } from "@/components/biz/Alert"
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
import { useOpportunities } from "@/hooks/useOpportunities"
import { POOL_RELEASE_REASONS } from "@/lib/customer"
import { isFinalStage } from "@/lib/pipeline"
import { pickReason } from "@/lib/templates"
import { defaultScope } from "@/lib/views"
import type { CustomerDetail, Role } from "@/types/api"

/** 退回公海（B5）：写明原因；有进行中商机时打开就说明原因并禁用确认（后端同样 42201 拒绝） */
export function ReleaseDialog({
  customer,
  role,
  open,
  onOpenChange,
}: {
  customer: CustomerDetail
  role: Role
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [reason, setReason] = useState("")
  const release = useReleaseCustomer(customer.id)
  // 有进行中的商机不能退回（后端 42201 has_open_opportunities）：打开时就说明，不等点了才报错
  const opps = useOpportunities({ view: defaultScope(role), customer_id: customer.id, page_size: 100 }, open)
  const openOpps = (opps.data?.items ?? []).filter((o) => o.customer.id === customer.id && !isFinalStage(o.stage))
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
            「{customer.name}」退回后没有负责人，本团队的销售可以领取，主管也可以直接分配。联系人和跟进记录会保留；还没成交的报价会关闭，未完成的待办会标为完成。
          </DialogDescription>
        </DialogHeader>
        {openOpps.length ? (
          <Alert tone="warn" title={`还有 ${openOpps.length} 个进行中的商机，不能退回`}>
            先把「
            {openOpps
              .slice(0, 3)
              .map((o) => o.name)
              .join("」「")}
            」{openOpps.length > 3 ? ` 等 ${openOpps.length} 个商机` : ""}
            标记为赢单 / 输单，或请主管转给同事。
          </Alert>
        ) : null}
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
            disabled={!reason.trim() || release.isPending || openOpps.length > 0 || opps.isPending}
            onClick={() => release.mutate({ reason: reason.trim() }, { onSuccess: close })}
          >
            确认退回
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
