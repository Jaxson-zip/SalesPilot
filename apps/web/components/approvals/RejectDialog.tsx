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
import type { ApprovalItem } from "@/types/api"

/** 驳回审批：可填写意见（报价驳回后退回草稿，报销驳回后为已驳回） */
export function RejectDialog({
  approval,
  pending,
  onCancel,
  onConfirm,
}: {
  approval: ApprovalItem | null
  pending?: boolean
  onCancel: () => void
  onConfirm: (comment: string) => void
}) {
  const [comment, setComment] = useState("")
  const close = () => {
    setComment("")
    onCancel()
  }
  return (
    <Dialog open={approval !== null} onOpenChange={(o) => !o && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>驳回审批</DialogTitle>
          <DialogDescription>
            {approval?.target_type === "quote"
              ? `报价单 ${approval.target.code} 驳回后退回草稿，销售修改后可重新提交。`
              : `报销 ${approval?.target.code ?? ""} 驳回后状态为「已驳回」。`}
          </DialogDescription>
        </DialogHeader>
        <Textarea
          autoFocus
          rows={3}
          maxLength={500}
          value={comment}
          placeholder="审批意见（可选），例如：维保改为 1 年后重新提交"
          onChange={(e) => setComment(e.target.value)}
        />
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button
            variant="destructive"
            disabled={pending}
            onClick={() => {
              onConfirm(comment.trim())
              setComment("")
            }}
          >
            确认驳回
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
