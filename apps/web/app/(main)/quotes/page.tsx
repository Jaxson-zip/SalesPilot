"use client"

import { FileText, Plus, Sparkles } from "lucide-react"

import { ComingSoon } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"

export default function QuotesPage() {
  return (
    <PageFrame
      title="报价单"
      icon={FileText}
      actions={
        <>
          <FrameAction icon={Plus} label="手动新建" />
          <FrameAction icon={Sparkles} label="AI 出方案" href="/ai" primary />
        </>
      }
    >
      <ComingSoon description="报价单列表（DataGrid）待接入 GET /api/quotes。" />
    </PageFrame>
  )
}
