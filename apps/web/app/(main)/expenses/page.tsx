"use client"

import { Plus, Receipt } from "lucide-react"

import { ComingSoon } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"

export default function ExpensesPage() {
  return (
    <PageFrame title="报销" icon={Receipt} actions={<FrameAction icon={Plus} label="新建报销" primary />}>
      <ComingSoon description="报销列表（DataGrid）、ExpenseSheet 与 PolicyCheckAlert 待实现。" />
    </PageFrame>
  )
}
