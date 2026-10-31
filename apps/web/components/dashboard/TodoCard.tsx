"use client"

import { Tag } from "@/components/biz/Tag"
import { TaskRow } from "@/components/tasks/TaskList"
import { Skeleton } from "@/components/ui/skeleton"
import { usePermissions } from "@/hooks/usePermissions"
import { useCompleteTask, useTasks } from "@/hooks/useTasks"
import { isNotImplemented } from "@/lib/errors"
import { mergeTodoTasks, taskHref } from "@/lib/tasks"
import type { DataView } from "@/types/api"

const MAX_ROWS = 8

/** 工作台「待办」（原型 TaskList，v3 §12）：今天到期 + 已逾期的未完成任务，可直接勾选完成，点标题跳到商机 / 客户 */
export function TodoCard({ view, title = "待办" }: { view: DataView; title?: string }) {
  const { canEdit } = usePermissions()
  const today = useTasks({ view, status: "open", due: "today" })
  const overdue = useTasks({ view, status: "open", due: "overdue" })
  const { complete, pendingId } = useCompleteTask()
  const items = mergeTodoTasks(overdue.data?.items ?? [], today.data?.items ?? [])
  const overdueCount = items.filter((t) => t.overdue).length
  const error = today.error ?? overdue.error

  let body
  if (today.isPending || overdue.isPending) {
    body = [0, 1, 2].map((i) => <Skeleton key={i} className="m-1 h-7" />)
  } else if (error) {
    body = (
      <div className="px-2.5 py-6 text-center text-zinc-500">
        {isNotImplemented(error) ? "任务接口后端开发中" : "待办加载失败"}
      </div>
    )
  } else if (items.length === 0) {
    body = <div className="px-2.5 py-6 text-center text-zinc-400">今天没有到期或逾期的任务</div>
  } else {
    body = items
      .slice(0, MAX_ROWS)
      .map((t) => (
        <TaskRow
          key={t.id}
          t={t}
          showSubject
          showOwner={view !== "mine"}
          href={taskHref(t)}
          canComplete={canEdit(t.owner?.id)}
          onComplete={complete}
          completing={pendingId === t.id}
        />
      ))
  }

  return (
    <div className="min-w-0 rounded-lg border border-zinc-200">
      <div className="flex h-10 items-center gap-2 border-b border-zinc-100 px-4">
        <span className="font-medium">{title}</span>
        {items.length ? <span className="text-zinc-400 tabular-nums">{items.length}</span> : null}
        <span className="flex-1" />
        {overdueCount ? <Tag color="red">逾期 {overdueCount}</Tag> : null}
      </div>
      <div className="p-1.5">{body}</div>
      {items.length > MAX_ROWS ? (
        <div className="border-t border-zinc-100 px-4 py-2 text-xs text-zinc-400">
          还有 {items.length - MAX_ROWS} 项，可在对应商机 / 客户里查看
        </div>
      ) : null}
    </div>
  )
}
