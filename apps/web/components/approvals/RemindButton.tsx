"use client"

import { BellRing } from "lucide-react"

import { COLLAPSE } from "@/components/biz/PageFrame"
import { Button } from "@/components/ui/button"
import { useRemindApproval } from "@/hooks/useApprovals"

/** 催办：报价 / 报销等主管审批时，负责人提醒本团队主管（站内通知，30 分钟一次） */
export function RemindButton({
  targetType,
  targetId,
  collapse = "sm",
}: {
  targetType: "quote" | "expense"
  targetId: string
  collapse?: keyof typeof COLLAPSE
}) {
  const remind = useRemindApproval()
  return (
    <Button
      size="sm"
      variant="outline"
      disabled={remind.isPending}
      onClick={() => remind.mutate({ target_type: targetType, target_id: targetId })}
      title="提醒主管尽快审批"
      className={COLLAPSE[collapse].button}
    >
      <BellRing />
      <span className={COLLAPSE[collapse].label}>催一下主管</span>
    </Button>
  )
}
