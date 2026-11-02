"use client"

import { CircleCheck, Inbox, Search, Stamp } from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { ApprovalRow } from "@/components/approvals/ApprovalRow"
import { RejectDialog } from "@/components/approvals/RejectDialog"
import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { EmptyState } from "@/components/biz/EmptyState"
import { SimpleSelect } from "@/components/biz/FormControls"
import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { LINE_TABS_LIST, LINE_TABS_TRIGGER } from "@/components/biz/RecordTabs"
import { RoleGate } from "@/components/shell/RoleGate"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useApprovals, useBatchDecide, useDecideApproval } from "@/hooks/useApprovals"
import {
  APPROVAL_SORT_LABEL,
  filterApprovals,
  sortApprovals,
  summarizeApprovals,
  approvalAmountText,
  type ApprovalSort,
  type ApprovalSummary,
  type ApprovalTypeFilter,
} from "@/lib/approvals"
import { approveConfirm } from "@/lib/confirm-texts"
import { formatFen } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { ApprovalItem, ApprovalTab } from "@/types/api"

const DONE_PAGE = 20
const MAX = 100

/** 待处理工具栏：搜索、类型（带数量）、排序 */
function Toolbar({
  q,
  onQ,
  type,
  onType,
  sort,
  onSort,
  counts,
}: {
  q: string
  onQ: (v: string) => void
  type: ApprovalTypeFilter
  onType: (v: ApprovalTypeFilter) => void
  sort: ApprovalSort
  onSort: (v: ApprovalSort) => void
  counts: ApprovalSummary
}) {
  const chips: { value: ApprovalTypeFilter; label: string; n: number }[] = [
    { value: "all", label: "全部", n: counts.count },
    { value: "expense", label: "报销", n: counts.byType.expense },
    { value: "quote", label: "报价", n: counts.byType.quote },
  ]
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-zinc-100 px-4 py-2.5 sm:px-5">
      <div className="relative w-full sm:w-64">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-zinc-400" />
        <Input
          value={q}
          onChange={(e) => onQ(e.target.value)}
          placeholder="搜单号、客户、申请人"
          aria-label="搜索审批"
          className="h-8 pl-8"
        />
      </div>
      <div role="group" aria-label="审批类型" className="flex items-center gap-1">
        {chips.map((c) => (
          <button
            key={c.value}
            type="button"
            aria-pressed={type === c.value}
            onClick={() => onType(c.value)}
            className={cn(
              "h-8 rounded-md px-2.5 text-sm transition-colors",
              type === c.value ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100",
            )}
          >
            {c.label} <span className="tabular-nums opacity-70">{c.n}</span>
          </button>
        ))}
      </div>
      <SimpleSelect
        value={sort}
        onChange={onSort}
        size="sm"
        ariaLabel="排序"
        className="ml-auto w-36"
        options={(Object.keys(APPROVAL_SORT_LABEL) as ApprovalSort[]).map((k) => ({
          value: k,
          label: APPROVAL_SORT_LABEL[k],
        }))}
      />
    </div>
  )
}

/**
 * 审批列表。待处理：一次取回（最多 100 条），可搜索、按类型筛选、按金额 / 超标排序，
 * 顶部汇总条数与金额，勾选后批量通过 / 驳回；已处理：每次 20 条，「加载更多」。
 */
function ApprovalList({
  tab,
  focus,
  onFocusMissing,
}: {
  tab: ApprovalTab
  /** 通知带来的审批 id：在列表里定位 */
  focus?: string | null
  /** 当前列表里没有这一条（多半已经处理过） */
  onFocusMissing?: () => void
}) {
  const pending = tab === "pending"
  const [size, setSize] = useState(pending ? MAX : DONE_PAGE)
  const query = useApprovals(tab, true, size)
  const decide = useDecideApproval()
  const batch = useBatchDecide()
  const [rejecting, setRejecting] = useState<ApprovalItem | null>(null)
  const [batchRejecting, setBatchRejecting] = useState(false)
  const { ask, dialog } = useConfirmAction()
  const [q, setQ] = useState("")
  const [type, setType] = useState<ApprovalTypeFilter>("all")
  const [sort, setSort] = useState<ApprovalSort>("oldest")
  const [picked, setPicked] = useState<Set<string>>(new Set())

  const all = useMemo(() => query.data?.items ?? [], [query.data])
  const shown = useMemo(
    () => (pending ? sortApprovals(filterApprovals(all, type, q), sort) : all),
    [pending, all, type, q, sort],
  )
  const counts = useMemo(() => summarizeApprovals(filterApprovals(all, "all", q)), [all, q])
  const sum = useMemo(() => summarizeApprovals(shown), [shown])
  // 只算还在当前列表里的勾选（筛选掉的不算）
  const selected = shown.filter((a) => picked.has(a.id))
  const selectedSum = summarizeApprovals(selected)
  const allPicked = shown.length > 0 && selected.length === shown.length
  const focusFound = Boolean(focus && all.some((a) => a.id === focus))
  useEffect(() => {
    if (focus && query.data && !focusFound) onFocusMissing?.()
  }, [focus, query.data, focusFound, onFocusMissing])

  const approve = (a: ApprovalItem) =>
    ask({
      ...approveConfirm(a.target.code, a.target_type),
      onConfirm: () => decide.mutate({ id: a.id, decision: "approve" }),
    })
  const approveBatch = () =>
    ask({
      title: `批量通过 ${selected.length} 条`,
      description: `${approvalAmountText(selectedSum)}。通过后报价单可以发送客户、报销进入打款流程，结果不能撤回。`,
      confirmLabel: "确认通过",
      onConfirm: () =>
        batch.mutate(
          { ids: selected.map((a) => a.id), decision: "approve" },
          { onSuccess: () => setPicked(new Set()) },
        ),
    })
  const toggle = (id: string, v: boolean) =>
    setPicked((s) => {
      const n = new Set(s)
      if (v) n.add(id)
      else n.delete(id)
      return n
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
  if (all.length === 0)
    return pending ? (
      <EmptyState icon={CircleCheck} title="没有待处理的审批" description="超出规则的报价和报销会出现在这里。" />
    ) : (
      <EmptyState icon={Inbox} title="还没有已处理的审批" />
    )

  const total = query.data.total
  return (
    <>
      {pending ? (
        <>
          <Toolbar q={q} onQ={setQ} type={type} onType={setType} sort={sort} onSort={setSort} counts={counts} />
          <div className="flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1 border-b border-zinc-100 bg-zinc-50/60 px-4 py-2 sm:px-5">
            <Checkbox
              aria-label="全选"
              checked={allPicked ? true : selected.length ? "indeterminate" : false}
              onCheckedChange={(v) => setPicked(v === true ? new Set(shown.map((a) => a.id)) : new Set())}
            />
            {selected.length ? (
              <>
                <span>
                  已选 <b className="tabular-nums">{selected.length}</b> 条 ·{" "}
                  <b className="tabular-nums">{approvalAmountText(selectedSum)}</b>
                </span>
                <div className="ml-auto flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={batch.isPending}
                    onClick={() => setBatchRejecting(true)}
                  >
                    批量驳回
                  </Button>
                  <Button size="sm" disabled={batch.isPending} onClick={approveBatch}>
                    {batch.isPending ? "处理中…" : `批量通过 ${selected.length}`}
                  </Button>
                </div>
              </>
            ) : (
              <span className="text-zinc-500">
                共 <b className="text-zinc-800 tabular-nums">{sum.count}</b> 条 ·{" "}
                <b className="text-zinc-800 tabular-nums">{approvalAmountText(sum)}</b>
                {sum.over ? (
                  <>
                    {" "}
                    · 其中超标 <b className="text-red-600 tabular-nums">{formatFen(sum.over)}</b>
                  </>
                ) : null}
                {total > all.length ? `（先显示最早的 ${all.length} 条，共 ${total} 条）` : ""}
              </span>
            )}
          </div>
        </>
      ) : null}
      {shown.length === 0 ? (
        <EmptyState icon={Inbox} title="没有符合条件的审批" description="换个关键词或类型试试。" />
      ) : (
        shown.map((a) => (
          <ApprovalRow
            key={a.id}
            a={a}
            busy={(decide.isPending && decide.variables?.id === a.id) || batch.isPending}
            onApprove={() => approve(a)}
            onReject={() => setRejecting(a)}
            selected={pending ? picked.has(a.id) : undefined}
            onSelectedChange={pending ? (v) => toggle(a.id, v) : undefined}
            focused={a.id === focus}
          />
        ))
      )}
      {!pending && total > all.length && size < MAX ? (
        <div className="py-3 text-center">
          <Button
            variant="ghost"
            size="sm"
            className="text-zinc-500"
            disabled={query.isFetching}
            onClick={() => setSize((n) => Math.min(n + DONE_PAGE, MAX))}
          >
            {query.isFetching ? "加载中…" : `加载更多（还有 ${total - all.length} 条）`}
          </Button>
        </div>
      ) : null}
      {dialog}
      <RejectDialog
        approval={rejecting}
        batch={batchRejecting ? selected.length : 0}
        pending={decide.isPending || batch.isPending}
        onCancel={() => {
          setRejecting(null)
          setBatchRejecting(false)
        }}
        onConfirm={(comment) => {
          if (batchRejecting)
            batch.mutate(
              { ids: selected.map((a) => a.id), decision: "reject", comment: comment || undefined },
              {
                onSuccess: () => {
                  setBatchRejecting(false)
                  setPicked(new Set())
                },
              },
            )
          else if (rejecting)
            decide.mutate(
              { id: rejecting.id, decision: "reject", comment: comment || undefined },
              { onSuccess: () => setRejecting(null) },
            )
        }}
      />
    </>
  )
}

function ApprovalCenter() {
  const [tab, setTab] = useState<ApprovalTab>("pending")
  const pending = useApprovals("pending")
  const count = pending.data?.total
  // 从待审批 / 催办通知跳转过来：/approvals?id=<审批 id>，待处理里没有就去已处理里找
  const [focus, setFocus] = useState<string | null>(null)
  useEffect(() => {
    setFocus(new URLSearchParams(window.location.search).get("id"))
  }, [])
  const onFocusMissing = useCallback(() => {
    if (tab === "pending") return setTab("done")
    toast.info("这条审批不在最近的记录里，可能已被处理或撤回")
    setFocus(null)
  }, [tab])
  return (
    <Tabs
      value={tab}
      onValueChange={(v) => {
        setFocus(null) // 用户自己切标签：不再定位通知里的那一条
        setTab(v === "done" ? "done" : "pending")
      }}
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
        <ApprovalList key={tab} tab={tab} focus={focus} onFocusMissing={onFocusMissing} />
      </div>
    </Tabs>
  )
}

/** 审批中心（仅销售主管）：待处理 / 已处理，报销显示附件，带审批建议（按客户等级、超标次数生成） */
export default function ApprovalsPage() {
  const { role } = useSession()
  return (
    <PageFrame title="审批" icon={Stamp}>
      <RoleGate roles={["manager"]} lockedText="审批仅销售主管可以处理">
        {role === "manager" ? <ApprovalCenter /> : null}
      </RoleGate>
    </PageFrame>
  )
}
