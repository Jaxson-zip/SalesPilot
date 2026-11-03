"use client"

import Link from "next/link"

import { Tag } from "@/components/biz/Tag"
import { TaskRow } from "@/components/tasks/TaskList"
import { Skeleton } from "@/components/ui/skeleton"
import { useTodoItems } from "@/hooks/useDashboard"
import { usePermissions } from "@/hooks/usePermissions"
import { useCompleteTask, useTasks } from "@/hooks/useTasks"
import { mergeTodoTasks, taskHref } from "@/lib/tasks"
import { TODO_KIND_LABEL, todoWhen } from "@/lib/todos"
import { cn } from "@/lib/utils"
import type { DataView, TodoItem } from "@/types/api"

const MAX_ROWS = 8

/** 回款、日报、待审批：没有勾选框，点标题去对应页面处理，处理完自动消失 */
function TodoItemRow({ t }: { t: TodoItem }) {
  const sub = [t.subject, t.detail].filter(Boolean).join(" · ")
  return (
    <div className="flex min-h-9 items-center gap-2.5 rounded-md px-2 hover:bg-zinc-50">
      <span aria-hidden className={cn("size-1.5 shrink-0 rounded-full", t.overdue ? "bg-red-500" : "bg-amber-400")} />
      <div className="flex min-w-0 flex-1 flex-col py-1.5">
        <Link href={t.link} className="truncate hover:underline">
          {t.title}
        </Link>
        {sub ? <div className="truncate text-xs text-zinc-400">{sub}</div> : null}
      </div>
      <span className="shrink-0 text-xs text-zinc-400">{TODO_KIND_LABEL[t.kind]}</span>
      <span className={cn("shrink-0 text-xs", t.overdue ? "text-red-600" : "text-zinc-500")}>{todoWhen(t)}</span>
    </div>
  )
}

/**
 * 工作台「待办」（原型 TaskList，v3 §12）：今天到期 + 已逾期的未完成任务，可直接勾选完成，点标题跳到商机 / 客户；
 * 上面是回款逾期 / 今天到期、今天的日报、待审批（GET /api/dashboard/todos）
 */
export function TodoCard({ view, title = "待办" }: { view: DataView; title?: string }) {
  const { canEdit } = usePermissions()
  const today = useTasks({ view, status: "open", due: "today" })
  const overdue = useTasks({ view, status: "open", due: "overdue" })
  const extra = useTodoItems(view)
  const { complete, pendingId } = useCompleteTask()
  const tasks = mergeTodoTasks(overdue.data?.items ?? [], today.data?.items ?? [])
  const extras = extra.data ?? []
  const total = extras.length + tasks.length
  const overdueCount = tasks.filter((t) => t.overdue).length + extras.filter((t) => t.overdue).length
  const error = today.error ?? overdue.error ?? extra.error

  let body
  if (today.isPending || overdue.isPending || extra.isPending) {
    body = [0, 1, 2].map((i) => <Skeleton key={i} className="m-1 h-7" />)
  } else if (error) {
    body = <div className="px-2.5 py-6 text-center text-zinc-500">待办加载失败</div>
  } else if (total === 0) {
    body = <div className="px-2.5 py-6 text-center text-zinc-400">今天没有到期或逾期的事项</div>
  } else {
    const shownExtras = extras.slice(0, MAX_ROWS)
    body = [
      ...shownExtras.map((t) => <TodoItemRow key={`${t.kind}:${t.link}:${t.title}`} t={t} />),
      ...tasks
        .slice(0, MAX_ROWS - shownExtras.length)
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
        )),
    ]
  }

  return (
    <div className="min-w-0 rounded-lg border border-zinc-200">
      <div className="flex h-10 items-center gap-2 border-b border-zinc-100 px-4">
        <span className="font-medium">{title}</span>
        {total ? <span className="text-zinc-400 tabular-nums">{total}</span> : null}
        <span className="flex-1" />
        {overdueCount ? <Tag color="red">逾期 {overdueCount}</Tag> : null}
      </div>
      <div className="p-1.5">{body}</div>
      {total > MAX_ROWS ? (
        <div className="border-t border-zinc-100 px-4 py-2 text-xs text-zinc-400">
          还有 {total - MAX_ROWS} 项，可在对应商机 / 客户 / 合同里查看
        </div>
      ) : null}
    </div>
  )
}
