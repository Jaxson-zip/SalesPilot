"use client"

import { LayoutDashboard, Plus, Sparkles } from "lucide-react"

import { ComingSoon } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"

export default function DashboardPage() {
  return (
    <PageFrame
      title="工作台"
      icon={LayoutDashboard}
      actions={
        <>
          <FrameAction icon={Sparkles} label="问 AI" href="/ai" />
          <FrameAction icon={Plus} label="出方案" href="/ai" primary />
        </>
      }
    >
      <ComingSoon description="StatCard ×4、FunnelChart、TaskList、ActivityFeed 待接入工作台接口。" />
    </PageFrame>
  )
}
