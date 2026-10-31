"use client"

import { Plus } from "lucide-react"
import Link from "next/link"
import { useEffect, useRef, useState } from "react"

import { AddTaskDialog } from "@/components/tasks/AddTaskDialog"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Skeleton } from "@/components/ui/skeleton"
import { useCompleteTask, useTasks } from "@/hooks/useTasks"
import { isNotImplemented } from "@/lib/errors"
import { dueText, isTaskOverdue, TASK_TYPE_LABEL } from "@/lib/tasks"
import { cn } from "@/lib/utils"
import { defaultScope } from "@/lib/views"
import type { TaskItem, TaskSubjectType } from "@/types/api"

/** 一行任务：勾选完成（可撤销）+ 标题 + 类型 / 到期；逾期红色 */
export function TaskRow({
  t,
  canComplete,
  href,
  showSubject,
  showOwner,
  onComplete,
  completing,
  focused,
}: {
  t: TaskItem
  canComplete: boolean
  /** 从通知 / 待办点进来的那条：滚到可见处并高亮 */
  focused?: boolean
  /** 点标题跳转（工作台待办：跳到对应商机 / 客户） */
  href?: string
  showSubject?: boolean
  /** 团队待办：显示负责人 */
  showOwner?: boolean
  onComplete: (t: TaskItem) => void
  completing?: boolean
}) {
  const overdue = isTaskOverdue(t)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (focused) ref.current?.scrollIntoView({ block: "center", behavior: "smooth" })
  }, [focused])
  const title = href ? (
    <Link href={href} className="truncate hover:underline">
      {t.title}
    </Link>
  ) : (
    <span className="truncate">{t.title}</span>
  )
  return (
    <div
      ref={ref}
      data-focused={focused || undefined}
      className={cn(
        "flex min-h-9 items-center gap-2.5 rounded-md px-2 hover:bg-zinc-50",
        focused && "bg-amber-50 ring-1 ring-amber-300 hover:bg-amber-50",
      )}
    >
      {canComplete ? (
        <Checkbox
          aria-label={`完成：${t.title}`}
          checked={false}
          disabled={completing}
          onCheckedChange={(v) => v === true && onComplete(t)}
        />
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col py-1.5">
        <div className="flex min-w-0 items-center gap-1.5">{title}</div>
        {showSubject || showOwner ? (
          <div className="truncate text-xs text-zinc-400">
            {[showSubject ? t.subject_name : null, showOwner ? (t.owner?.name ?? "未分配") : null]
              .filter(Boolean)
              .join(" · ")}
          </div>
        ) : null}
      </div>
      <span className="shrink-0 text-xs text-zinc-400">{TASK_TYPE_LABEL[t.type] ?? t.type}</span>
      <span className={cn("shrink-0 text-xs tabular-nums", overdue ? "text-red-600" : "text-zinc-500")}>
        {dueText(t.due_at, overdue)}
      </span>
    </div>
  )
}

/**
 * 某个商机 / 客户的未完成任务 +「添加下一步」（v3 §12）。
 * editable：本人负责的记录才能添加和完成（契约 §0）。
 */
export function SubjectTasks({
  subjectType,
  subjectId,
  subjectName,
  editable,
  focusId,
}: {
  subjectType: TaskSubjectType
  subjectId: string
  subjectName: string
  editable: boolean
  /** 要定位的任务 id（地址里的 task 参数） */
  focusId?: string | null
}) {
  const { role } = useSession()
  const [adding, setAdding] = useState(false)
  const q = useTasks({ view: defaultScope(role), status: "open", subject_type: subjectType, subject_id: subjectId })
  const { complete, pendingId } = useCompleteTask()
  // 接口没有 subject 过滤时兜底
  const items = (q.data?.items ?? []).filter((t) => t.subject_id === subjectId && !t.done)

  let body
  if (q.isPending) body = <Skeleton className="h-9 w-full" />
  else if (q.isError)
    body = <div className="px-2 text-zinc-400">{isNotImplemented(q.error) ? "任务接口后端开发中" : "任务加载失败"}</div>
  else if (items.length === 0)
    body = (
      <div className="rounded-md bg-amber-50 px-2.5 py-2 text-amber-800">
        未安排下一步{editable ? "，建议约好下一次跟进" : ""}
      </div>
    )
  else
    body = items.map((t) => (
      <TaskRow
        key={t.id}
        t={t}
        canComplete={editable}
        onComplete={complete}
        completing={pendingId === t.id}
        focused={t.id === focusId}
      />
    ))

  const pending = q.isError && isNotImplemented(q.error)
  return (
    <div>
      <div className="mb-1.5 flex h-7 items-center justify-between">
        <span className="text-zinc-500">下一步</span>
        {editable && !pending ? (
          <Button variant="ghost" size="xs" className="h-7 text-zinc-600" onClick={() => setAdding(true)}>
            <Plus />
            添加下一步
          </Button>
        ) : null}
      </div>
      <div className="space-y-0.5">{body}</div>
      {editable ? (
        <AddTaskDialog
          open={adding}
          onOpenChange={setAdding}
          subjectType={subjectType}
          subjectId={subjectId}
          subjectName={subjectName}
        />
      ) : null}
    </div>
  )
}
