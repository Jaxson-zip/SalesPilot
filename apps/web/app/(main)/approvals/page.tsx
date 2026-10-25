"use client"

import { Stamp } from "lucide-react"

import { ComingSoon } from "@/components/biz/EmptyState"
import { PageFrame } from "@/components/biz/PageFrame"
import { RoleGate } from "@/components/shell/RoleGate"

export default function ApprovalsPage() {
  return (
    <PageFrame title="审批" icon={Stamp}>
      <RoleGate roles={["manager"]} lockedText="仅销售主管可见，可在左下角切换角色">
        <ComingSoon description="ApprovalItem（带 AI 建议）列表待接入审批接口。" />
      </RoleGate>
    </PageFrame>
  )
}
