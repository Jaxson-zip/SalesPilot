"use client"

import { Building2, Ellipsis, PencilLine, Sparkles } from "lucide-react"
import { useParams } from "next/navigation"

import { ComingSoon } from "@/components/biz/EmptyState"
import { Crumb, FrameAction, PageFrame } from "@/components/biz/PageFrame"

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>()
  return (
    <PageFrame
      crumb={<Crumb parent="客户" href="/customers" icon={Building2} current={decodeURIComponent(id)} />}
      actions={
        <>
          <FrameAction icon={Ellipsis} />
          <FrameAction icon={PencilLine} label="写跟进" />
          <FrameAction icon={Sparkles} label="为该客户出方案" href="/ai" primary />
        </>
      }
    >
      <ComingSoon description="RecordFields（左）+ Tabs / Timeline（右）待接入 GET /api/customers/{id}。" />
    </PageFrame>
  )
}
