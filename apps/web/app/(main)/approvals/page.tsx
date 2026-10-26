"use client"

import { CircleCheck, Inbox, Stamp } from "lucide-react"
import { useState } from "react"

import { ApprovalRow } from "@/components/approvals/ApprovalRow"
import { RejectDialog } from "@/components/approvals/RejectDialog"
import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { EmptyState } from "@/components/biz/EmptyState"
import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { LINE_TABS_LIST, LINE_TABS_TRIGGER } from "@/components/biz/RecordTabs"
import { RoleGate } from "@/components/shell/RoleGate"
import { useSession } from "@/components/shell/SessionProvider"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useApprovals, useDecideApproval } from "@/hooks/useApprovals"
import { approveConfirm } from "@/lib/confirm-texts"
import type { ApprovalItem, ApprovalTab } from "@/types/api"

function ApprovalList({ tab }: { tab: ApprovalTab }) {
  const query = useApprovals(tab)
  const decide = useDecideApproval()
  const [rejecting, setRejecting] = useState<ApprovalItem | null>(null)
  const { ask, dialog } = useConfirmAction()
  const approve = (a: ApprovalItem) =>
    ask({
      ...approveConfirm(a.target.code, a.target_type),
      onConfirm: () => decide.mutate({ id: a.id, decision: "approve" }),
    })

  if (query.isPending)
    return (
      <div className="space-y-3 p-5">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    )
  if (query.isError && !query.data)
    return (
      <QueryError error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} feature="审批" />
    )
  if (query.data.items.length === 0)
    return tab === "pending" ? (
      <EmptyState icon={CircleCheck} title="没有待处理的审批" description="超出规则的报价和报销会出现在这里。" />
    ) : (
      <EmptyState icon={Inbox} title="还没有已处理的审批" />
    )

  return (
    <>
      {query.data.items.map((a) => (
        <ApprovalRow
          key={a.id}
          a={a}
          busy={decide.isPending && decide.variables?.id === a.id}
          onApprove={() => approve(a)}
          onReject={() => setRejecting(a)}
        />
      ))}
      {dialog}
      <RejectDialog
        approval={rejecting}
        pending={decide.isPending}
        onCancel={() => setRejecting(null)}
        onConfirm={(comment) =>
          rejecting &&
          decide.mutate(
            { id: rejecting.id, decision: "reject", comment: comment || undefined },
            { onSuccess: () => setRejecting(null) },
          )
        }
      />
    </>
  )
}

function ApprovalCenter() {
  const [tab, setTab] = useState<ApprovalTab>("pending")
  const pending = useApprovals("pending")
  const count = pending.data?.total
  return (
    <Tabs
      value={tab}
      onValueChange={(v) => setTab(v === "done" ? "done" : "pending")}
      className="flex min-h-0 flex-1 flex-col gap-0"
    >
      <TabsList variant="line" className={LINE_TABS_LIST}>
        <TabsTrigger value="pending" className={LINE_TABS_TRIGGER}>
          待处理{count ? ` ${count}` : ""}
        </TabsTrigger>
        <TabsTrigger value="done" className={LINE_TABS_TRIGGER}>
          已处理
        </TabsTrigger>
      </TabsList>
      <div className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
        <ApprovalList key={tab} tab={tab} />
      </div>
    </Tabs>
  )
}

/** 审批中心（仅销售主管）：待处理 / 已处理，报销显示附件，带 AI 建议 */
export default function ApprovalsPage() {
  const { role } = useSession()
  return (
    <PageFrame title="审批" icon={Stamp}>
      <RoleGate roles={["manager"]} lockedText="仅销售主管可见，可在左下角切换角色">
        {role === "manager" ? <ApprovalCenter /> : null}
      </RoleGate>
    </PageFrame>
  )
}
