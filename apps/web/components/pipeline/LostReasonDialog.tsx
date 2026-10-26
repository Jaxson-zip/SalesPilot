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
import { useTemplates } from "@/hooks/useTemplates"
import { pickReason } from "@/lib/templates"
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
  const reasons = useTemplates().data?.lost_reasons ?? []
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
        <QuickChips
          label="常见输单原因"
          items={reasons.map((r) => ({ key: r, label: r }))}
          onPick={(r) => setReason((cur) => pickReason(cur, r))}
        />
        <Textarea
          autoFocus
          rows={3}
          value={reason}
          maxLength={500}
          placeholder="选一个常见原因，再补充具体情况，例如：对方报价低 20%"
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
