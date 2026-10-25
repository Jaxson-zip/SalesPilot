"use client"

import { Building2, Ellipsis, Plus, Star, Tag as TagIcon, User } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { DataGrid } from "@/components/biz/DataGrid"
import { EmptyState, ErrorState } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { ViewBar, type ViewOption } from "@/components/biz/ViewBar"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { useCustomers } from "@/hooks/useCustomers"
import type { CustomerView } from "@/types/api"

import { customerColumns } from "./columns"

const FILTER_FIELDS = [
  { label: "客户名称", icon: Building2 },
  { label: "行业", icon: TagIcon },
  { label: "等级", icon: Star },
  { label: "负责人", icon: User },
]

function isView(v: string): v is CustomerView {
  return v === "mine" || v === "team" || v === "all"
}

/** 客户列表（参考实现）：ViewBar + DataGrid，含骨架屏、空状态、错误状态 */
export default function CustomersPage() {
  const { isLead } = useSession()
  const [selected, setView] = useState<CustomerView>("mine")
  const views: ViewOption[] = isLead
    ? [
        { value: "mine", label: "我负责的" },
        { value: "team", label: "团队客户" },
      ]
    : [{ value: "mine", label: "我的客户" }]
  // 切换角色后原视图可能不可用（例如主管 → 销售），回落到第一个视图
  const view: CustomerView = views.some((v) => v.value === selected) ? selected : "mine"

  const query = useCustomers({ view, page: 1, page_size: 20 })
  const notReady = () => toast("新建客户 Sheet 开发中")

  return (
    <PageFrame
      title="客户"
      icon={Building2}
      actions={
        <>
          <FrameAction icon={Ellipsis} />
          <FrameAction icon={Plus} label="新建客户" primary onClick={notReady} />
        </>
      }
    >
      <ViewBar
        views={views}
        value={view}
        onValueChange={(v) => isView(v) && setView(v)}
        count={query.data?.total}
        fields={FILTER_FIELDS}
      />
      {query.isError && !query.data ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} />
      ) : (
        <DataGrid
          columns={customerColumns}
          data={query.data?.items ?? []}
          getRowId={(c) => c.id}
          loading={query.isPending}
          total={query.data?.total}
          onAddRow={notReady}
          empty={
            <EmptyState
              icon={Building2}
              title="还没有客户"
              description="可以新建客户，或在 AI 方案工作台里让 AI 帮你录入。"
              action={
                <Button size="sm" onClick={notReady}>
                  <Plus />
                  新建客户
                </Button>
              }
            />
          }
        />
      )}
    </PageFrame>
  )
}
