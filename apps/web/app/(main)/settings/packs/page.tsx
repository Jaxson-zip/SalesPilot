"use client"

import { Boxes, Plus } from "lucide-react"

import { ComingSoon } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { RoleGate } from "@/components/shell/RoleGate"
import { useSession } from "@/components/shell/SessionProvider"

export default function PacksPage() {
  const { role } = useSession()
  return (
    <PageFrame
      title="行业包配置"
      icon={Boxes}
      actions={role === "admin" ? <FrameAction icon={Plus} label="新增行业包" primary /> : null}
    >
      <RoleGate roles={["admin"]} lockedText="行业包由系统管理员统一配置，可在左下角切换为「系统管理员」查看">
        <ComingSoon description="PackCard（启用开关）与 ProductLineMapping 待实现。" />
      </RoleGate>
    </PageFrame>
  )
}
