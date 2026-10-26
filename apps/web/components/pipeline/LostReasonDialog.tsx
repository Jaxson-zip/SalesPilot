"use client"

import { useState } from "react"

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
import type { OpportunityItem } from "@/types/api"

/** 拖到「输单」时填写原因（契约：stage=lost 时 lost_reason 必填） */
export function LostReasonDialog({
  opp,
  onCancel,
  onConfirm,
}: {
  opp: OpportunityItem | null
  onCancel: () => void
  onConfirm: (reason: string) => void
}) {
  const [reason, setReason] = useState("")
  const close = () => {
    setReason("")
    onCancel()
  }
  return (
    <Dialog open={opp !== null} onOpenChange={(o) => !o && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>标记为输单</DialogTitle>
          <DialogDescription>「{opp?.name}」标记后为终态，不能再切换阶段。请填写输单原因，便于复盘。</DialogDescription>
        </DialogHeader>
        <Textarea
          autoFocus
          rows={3}
          value={reason}
          maxLength={500}
          placeholder="例如：客户预算削减，选择了价格更低的竞品"
          onChange={(e) => setReason(e.target.value)}
        />
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button
            variant="destructive"
            disabled={!reason.trim()}
            onClick={() => {
              onConfirm(reason.trim())
              setReason("")
            }}
          >
            确认输单
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
