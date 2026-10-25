"use client"

import { Ellipsis, Plus, Target } from "lucide-react"

import { ComingSoon } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"

export default function PipelinePage() {
  return (
    <PageFrame
      title="商机"
      icon={Target}
      actions={
        <>
          <FrameAction icon={Ellipsis} />
          <FrameAction icon={Plus} label="新建商机" primary />
        </>
      }
    >
      <ComingSoon description="Kanban（≥1024 五列等分；更窄时阶段切换 + 单列卡片）与 OpportunitySheet 待实现。" />
    </PageFrame>
  )
}
