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

/** 驳回审批：必须写原因，员工照着改（报价驳回后退回草稿，报销驳回后可修改再重新提交） */
export function RejectDialog({
  approval,
  batch = 0,
  pending,
  onCancel,
  onConfirm,
}: {
  approval: ApprovalItem | null
  /** 批量驳回的条数（>0 时忽略 approval，所有选中的单子用同一条意见） */
  batch?: number
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
    <Dialog open={approval !== null || batch > 0} onOpenChange={(o) => !o && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{batch ? `批量驳回 ${batch} 条` : "驳回审批"}</DialogTitle>
          <DialogDescription>
            {batch
              ? "选中的单子使用同一条原因：报价单退回草稿，报销可修改后重新提交。"
              : approval?.target_type === "quote"
                ? `报价单 ${approval.target.code} 驳回后退回草稿，销售修改后可重新提交。`
                : `报销 ${approval?.target.code ?? ""} 驳回后，员工可以修改、补票据再重新提交。`}
          </DialogDescription>
        </DialogHeader>
        <Textarea
          autoFocus
          rows={3}
          maxLength={500}
          value={comment}
          aria-label="驳回原因"
          placeholder={`驳回原因（必填，员工会看到），例如：${
            approval?.target_type === "quote" ? "维保改为 1 年后重新提交" : "人均超标，请把参与人补齐后重新提交"
          }`}
          onChange={(e) => setComment(e.target.value)}
        />
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button
            variant="destructive"
            disabled={pending || !comment.trim()}
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
