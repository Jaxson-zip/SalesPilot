"use client"

import { Calendar, Coins, Layers, Plus, Target, User } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { EmptyState } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { ViewBar } from "@/components/biz/ViewBar"
import { KanbanBoard } from "@/components/pipeline/KanbanBoard"
import { LostReasonDialog } from "@/components/pipeline/LostReasonDialog"
import { NewOpportunitySheet } from "@/components/pipeline/NewOpportunitySheet"
import { OpportunitySheet } from "@/components/pipeline/OpportunitySheet"
import { StageList } from "@/components/pipeline/StageList"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { useChangeStage, useOpportunities } from "@/hooks/useOpportunities"
import { checkStageMove, groupByStage } from "@/lib/pipeline"
import { resolveScope, scopeOptions } from "@/lib/views"
import type { OpportunityItem, OpportunityStage } from "@/types/api"

const FILTER_FIELDS = [
  { label: "阶段", icon: Layers },
  { label: "金额", icon: Coins },
  { label: "负责人", icon: User },
  { label: "预计成交", icon: Calendar },
]

/** 商机看板：≥1024 五列拖拽；<1024 阶段切换 + 单列 */
export default function PipelinePage() {
  const { role } = useSession()
  // 空串 → resolveScope 取当前角色的默认范围（主管默认团队）
  const [selected, setSelected] = useState("")
  const view = resolveScope(role, selected)
  const views = scopeOptions(role, "商机")

  const query = useOpportunities({ view, page: 1, page_size: 100 })
  const groups = useMemo(() => groupByStage(query.data?.items ?? []), [query.data])
  const change = useChangeStage()

  const [mobileStage, setMobileStage] = useState<OpportunityStage>("lead")
  const [openId, setOpenId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [losing, setLosing] = useState<OpportunityItem | null>(null)
  // Sheet 里显示最新缓存（乐观更新后阶段立即变化）
  const opened = query.data?.items.find((o) => o.id === openId) ?? null

  const move = (opp: OpportunityItem, to: OpportunityStage) => {
    const check = checkStageMove(opp.stage, to)
    if (!check.ok) return void toast.error(check.reason)
    if (to === "lost") return setLosing(opp)
    change.mutate({ id: opp.id, stage: to })
  }

  const empty = !query.isPending && !query.isError && (query.data?.items.length ?? 0) === 0
  let body
  if (query.isError && !query.data) {
    body = (
      <QueryError error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} feature="商机" />
    )
  } else if (empty) {
    body = (
      <EmptyState
        icon={Target}
        title="还没有商机"
        description="新建一个商机，或在 AI 方案工作台里让 AI 根据跟进记录创建。"
        action={
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus />
            新建商机
          </Button>
        }
      />
    )
  } else {
    const shared = { groups, loading: query.isPending, onOpen: (o: OpportunityItem) => setOpenId(o.id) }
    body = (
      <>
        <div className="hidden flex-1 overflow-x-hidden overflow-y-auto p-3 lg:block">
          <KanbanBoard {...shared} onCreate={() => setCreating(true)} onMove={move} />
        </div>
        <div className="flex-1 overflow-x-hidden overflow-y-auto lg:hidden">
          <StageList
            {...shared}
            stage={mobileStage}
            onStageChange={setMobileStage}
            onCreate={() => setCreating(true)}
          />
        </div>
      </>
    )
  }

  return (
    <PageFrame
      title="商机"
      icon={Target}
      actions={<FrameAction icon={Plus} label="新建商机" primary onClick={() => setCreating(true)} />}
    >
      <ViewBar
        views={views}
        value={view}
        onValueChange={setSelected}
        count={query.data?.total}
        fields={FILTER_FIELDS}
      />
      {body}
      <OpportunitySheet opp={opened} onClose={() => setOpenId(null)} onStageChange={move} changing={change.isPending} />
      <NewOpportunitySheet open={creating} onOpenChange={setCreating} />
      <LostReasonDialog
        opp={losing}
        onCancel={() => setLosing(null)}
        onConfirm={(reason) => {
          if (losing) change.mutate({ id: losing.id, stage: "lost", lost_reason: reason })
          setLosing(null)
        }}
      />
    </PageFrame>
  )
}
