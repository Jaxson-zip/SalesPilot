"use client"

import { Plus, Target } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { EmptyState } from "@/components/biz/EmptyState"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { ViewBar } from "@/components/biz/ViewBar"
import { KanbanBoard } from "@/components/pipeline/KanbanBoard"
import { NewOpportunitySheet } from "@/components/pipeline/NewOpportunitySheet"
import { OpportunitySheet } from "@/components/pipeline/OpportunitySheet"
import { StageList } from "@/components/pipeline/StageList"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { useListView } from "@/hooks/useListView"
import { useOpportunities } from "@/hooks/useOpportunities"
import { usePermissions } from "@/hooks/usePermissions"
import { useStageMove } from "@/hooks/useStageMove"
import { groupByStage, opportunityCsv, opportunityFilters, opportunitySort } from "@/lib/pipeline"
import { resolveScope, scopeOptions } from "@/lib/views"
import type { OpportunityItem, OpportunityStage } from "@/types/api"

/** 商机看板：≥1024 五列拖拽；<1024 阶段切换 + 单列 */
export default function PipelinePage() {
  const { role } = useSession()
  const { canCreate, canEdit } = usePermissions()
  // 空串 → resolveScope 取当前角色的默认范围（主管默认团队）
  const [selected, setSelected] = useState("")
  const view = resolveScope(role, selected)
  const views = scopeOptions(role, "商机")

  const query = useOpportunities({ view, page: 1, page_size: 100 })
  const all = useMemo(() => query.data?.items ?? [], [query.data])
  const filters = useMemo(() => opportunityFilters(all), [all])
  const lv = useListView({
    entity: "opportunities",
    page: "pipeline",
    rows: all,
    filters,
    sort: opportunitySort,
    csv: opportunityCsv,
    exportName: "商机",
  })
  // 筛选 / 排序后再分组：每列内的卡片顺序跟随排序
  const groups = useMemo(() => groupByStage(lv.rows), [lv.rows])
  const filtered = Object.keys(lv.bar.activeFilters).length > 0
  const { move, changing, dialogs } = useStageMove()

  const [mobileStage, setMobileStage] = useState<OpportunityStage>("lead")
  const [openId, setOpenId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  // 从工作台待办 / 通知跳转过来：/pipeline?opp=<id> 直接打开商机侧栏（不用 useSearchParams，避免整页需要 Suspense）
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("opp")
    if (id) setOpenId(id)
  }, [])
  const openCreate = canCreate ? () => setCreating(true) : undefined
  // Sheet 里显示最新缓存（乐观更新后阶段立即变化）
  const opened = query.data?.items.find((o) => o.id === openId) ?? null

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
        description={canCreate ? "新建一个商机，或在 AI 方案工作台里让 AI 根据跟进记录创建。" : undefined}
        action={
          canCreate ? (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus />
              新建商机
            </Button>
          ) : undefined
        }
      />
    )
  } else {
    const shared = {
      groups,
      loading: query.isPending,
      onOpen: (o: OpportunityItem) => setOpenId(o.id),
      showOwner: view !== "mine",
    }
    body = (
      <>
        <div className="hidden flex-1 overflow-x-hidden overflow-y-auto p-3 lg:block">
          <KanbanBoard {...shared} onCreate={openCreate} canDrag={(o) => canEdit(o.owner?.id)} onMove={move} />
        </div>
        <div className="flex-1 overflow-x-hidden overflow-y-auto lg:hidden">
          <StageList {...shared} stage={mobileStage} onStageChange={setMobileStage} onCreate={openCreate} />
        </div>
      </>
    )
  }

  return (
    <PageFrame
      title="商机"
      icon={Target}
      actions={
        canCreate ? <FrameAction icon={Plus} label="新建商机" primary onClick={() => setCreating(true)} /> : null
      }
    >
      <ViewBar
        views={views}
        value={view}
        onValueChange={setSelected}
        count={filtered ? lv.rows.length : query.data?.total}
        list={lv.bar}
      />
      {body}
      <OpportunitySheet
        opp={opened}
        editable={opened ? canEdit(opened.owner?.id) : false}
        onClose={() => setOpenId(null)}
        onStageChange={move}
        changing={changing}
      />
      <NewOpportunitySheet open={creating} onOpenChange={setCreating} />
      {dialogs}
    </PageFrame>
  )
}
