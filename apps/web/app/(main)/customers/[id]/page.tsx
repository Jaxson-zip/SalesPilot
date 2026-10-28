"use client"

import { Building2, Clock, Contact, FileText, Hand, PencilLine, Sparkles, Target, Undo2 } from "lucide-react"
import { useParams } from "next/navigation"
import { useRef, useState } from "react"

import { Alert } from "@/components/biz/Alert"
import { DataGrid } from "@/components/biz/DataGrid"
import { EmptyState } from "@/components/biz/EmptyState"
import { Crumb, FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { RecordTabs } from "@/components/biz/RecordTabs"
import { ContactsPanel } from "@/components/customers/ContactsPanel"
import { CustomerFields, CustomerOpportunities } from "@/components/customers/CustomerFields"
import { CustomerTimeline, FollowupComposer } from "@/components/customers/CustomerTimeline"
import { ReleaseDialog } from "@/components/customers/ReleaseDialog"
import { useSession } from "@/components/shell/SessionProvider"
import { Skeleton } from "@/components/ui/skeleton"
import { useClaimCustomer, useCustomer } from "@/hooks/useCustomers"
import { usePermissions } from "@/hooks/usePermissions"
import { useQuotes } from "@/hooks/useQuotes"
import { defaultScope } from "@/lib/views"
import type { Role } from "@/types/api"

import { quoteColumns } from "../../quotes/columns"

/** 客户的报价单：契约的 /api/quotes 没有 customer_id 参数，这里同时传参并在前端兜底过滤 */
function CustomerQuotes({ customerId, role }: { customerId: string; role: Role }) {
  const q = useQuotes({ view: defaultScope(role), customer_id: customerId, page_size: 50 })
  if (q.isError && !q.data) return <QueryError error={q.error} onRetry={() => void q.refetch()} feature="报价单" />
  const items = (q.data?.items ?? []).filter((x) => x.customer?.id === customerId)
  return (
    <div className="flex min-h-48 flex-col overflow-hidden rounded-lg border border-zinc-200">
      <DataGrid
        columns={quoteColumns}
        data={items}
        getRowId={(x) => x.id}
        loading={q.isPending}
        total={items.length}
        empty={<EmptyState icon={FileText} title="该客户还没有报价单" />}
      />
    </div>
  )
}

/** 客户记录页：左字段面板（字段 / 下一步）+ 右标签页（时间线 + 写跟进 / 商机 / 联系人 / 报价单） */
export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>()
  const customerId = decodeURIComponent(id)
  const { role, userId } = useSession()
  const { canFollowup: canWriteFollowup, canAiWrite, canEdit } = usePermissions()
  const query = useCustomer(customerId)
  const claim = useClaimCustomer(customerId)
  const [releasing, setReleasing] = useState(false)
  const [tab, setTab] = useState("timeline")
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const c = query.data
  // 公海客户（B5）：负责人为空，只读，领取后才能编辑和写跟进
  const inPool = Boolean(c) && !c?.owner
  const canFollowup = canWriteFollowup && !inPool
  const canRelease = Boolean(c?.owner) && (c?.owner?.id === userId || role === "manager")

  const writeFollowup = () => {
    setTab("timeline")
    // 标题行「写跟进」= 定位到时间线顶部的写跟进框（同一个入口，不另开表单）
    setTimeout(() => {
      composerRef.current?.scrollIntoView({ block: "center", behavior: "smooth" })
      composerRef.current?.focus({ preventScroll: true })
    }, 50)
  }

  let body
  if (query.isPending) {
    body = (
      <div className="space-y-3 p-4">
        <Skeleton className="h-10 w-56" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  } else if (query.isError) {
    body = (
      <QueryError
        error={query.error}
        onRetry={() => void query.refetch()}
        retrying={query.isFetching}
        feature="客户详情"
      />
    )
  } else {
    const cust = query.data
    body = (
      <div className="flex min-h-0 flex-1 flex-col overflow-x-hidden overflow-y-auto lg:flex-row lg:overflow-hidden">
        <div className="shrink-0 border-b border-zinc-200 p-4 lg:w-[340px] lg:overflow-y-auto lg:border-r lg:border-b-0">
          {inPool ? (
            <Alert tone="info" className="mb-3" title="公海客户">
              {role === "sales" ? "领取后才能编辑和写跟进。" : "可以在客户列表勾选后「转移负责人」分配给销售。"}
            </Alert>
          ) : null}
          <CustomerFields c={cust} editable={canEdit(cust.owner?.id)} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col lg:min-h-0">
          <RecordTabs
            value={tab}
            onValueChange={setTab}
            tabs={[
              {
                value: "timeline",
                label: "时间线",
                icon: Clock,
                content: (
                  <>
                    {canFollowup ? <FollowupComposer ref={composerRef} customerId={cust.id} /> : null}
                    <CustomerTimeline
                      customerId={cust.id}
                      role={role}
                      owner={cust.owner?.name ?? "—"}
                      canWrite={canFollowup}
                    />
                  </>
                ),
              },
              {
                value: "opportunities",
                label: "商机",
                icon: Target,
                content: <CustomerOpportunities customerId={cust.id} role={role} />,
              },
              {
                value: "contacts",
                label: "联系人",
                icon: Contact,
                content: <ContactsPanel customerId={cust.id} editable={canEdit(cust.owner?.id)} />,
              },
              {
                value: "quotes",
                label: "报价单",
                icon: FileText,
                content: <CustomerQuotes customerId={cust.id} role={role} />,
              },
            ]}
          />
        </div>
      </div>
    )
  }

  return (
    <PageFrame
      crumb={<Crumb parent="客户" href="/customers" icon={Building2} current={c?.name ?? "客户详情"} />}
      actions={
        <>
          {inPool && role === "sales" ? (
            <FrameAction icon={Hand} label="领取客户" primary onClick={() => !claim.isPending && claim.mutate()} />
          ) : null}
          {canRelease ? <FrameAction icon={Undo2} label="退回公海" onClick={() => setReleasing(true)} /> : null}
          {canFollowup ? <FrameAction icon={PencilLine} label="写跟进" onClick={writeFollowup} /> : null}
          {canAiWrite ? <FrameAction icon={Sparkles} label="为该客户出方案" href="/ai" primary /> : null}
        </>
      }
    >
      {body}
      {c && canRelease ? <ReleaseDialog customer={c} open={releasing} onOpenChange={setReleasing} /> : null}
    </PageFrame>
  )
}
