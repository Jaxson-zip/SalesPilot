"use client"

import { FileSignature, Info } from "lucide-react"

import { ComingSoon } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"

export default function ContractsPage() {
  return (
    <PageFrame title="合同与提成" icon={FileSignature} actions={<FrameAction icon={Info} label="提成规则" />}>
      <ComingSoon description="StatStrip、合同列表（DataGrid）与提成规则 Sheet 待实现。" />
    </PageFrame>
  )
}
