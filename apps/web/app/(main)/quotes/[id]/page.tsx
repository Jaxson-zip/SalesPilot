"use client"

import { Download, FileText, Send } from "lucide-react"
import { useParams } from "next/navigation"

import { ComingSoon } from "@/components/biz/EmptyState"
import { Crumb, FrameAction, PageFrame } from "@/components/biz/PageFrame"

export default function QuoteDetailPage() {
  const { id } = useParams<{ id: string }>()
  return (
    <PageFrame
      crumb={<Crumb parent="报价单" href="/quotes" icon={FileText} current={decodeURIComponent(id)} />}
      actions={
        <>
          <FrameAction icon={Download} label="导出 PDF" />
          <FrameAction icon={Send} label="发送客户" primary />
        </>
      }
    >
      <ComingSoon description="RecordFields（左）+ 物料清单 / 时间线 / 审批记录标签页（右）待实现。" />
    </PageFrame>
  )
}
