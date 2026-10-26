"use client"

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query"
import { useCallback } from "react"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { activityKeys, dashboardKeys } from "@/hooks/useDashboard"
import { api } from "@/lib/api"
import { UNDO_DURATION_MS, UNDO_LABEL } from "@/lib/stage-move"
import { taskDoneText } from "@/lib/tasks"
import type { Paged, TaskCreate, TaskItem, TaskListParams, TaskUpdate } from "@/types/api"

export const taskKeys = {
  all: ["tasks"] as const,
  list: (p: TaskListParams) => ["tasks", p] as const,
}

/** GET /api/tasks?view=&status=&due=&subject_type=&subject_id=（v3 §12） */
export function useTasks(params: TaskListParams, enabled = true) {
  return useQuery({
    queryKey: taskKeys.list(params),
    queryFn: ({ signal }) =>
      api.get<Paged<TaskItem>>(
        "/api/tasks",
        {
          view: params.view,
          status: params.status,
          due: params.due,
          subject_type: params.subject_type,
          subject_id: params.subject_id,
        },
        signal,
      ),
    enabled,
  })
}

/** 任务变化会影响：任务列表、商机的 next_task、工作台计数、动态 */
function invalidateTasks(qc: QueryClient): Promise<unknown> {
  return Promise.all([
    qc.invalidateQueries({ queryKey: taskKeys.all }),
    qc.invalidateQueries({ queryKey: ["opportunities"] }),
    qc.invalidateQueries({ queryKey: dashboardKeys.all }),
    qc.invalidateQueries({ queryKey: activityKeys.all }),
    qc.invalidateQueries({ queryKey: ["notifications"] }),
  ])
}

/** POST /api/tasks */
export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TaskCreate) => api.post<TaskItem>("/api/tasks", body),
    onSuccess: (t) => {
      toast.success("已添加下一步", { description: t?.title })
      void invalidateTasks(qc)
    },
    onError: notifyError,
  })
}

/** PATCH /api/tasks/{id} */
export function useUpdateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: TaskUpdate & { id: string }) => api.patch<TaskItem>(`/api/tasks/${id}`, body),
    onSettled: () => invalidateTasks(qc),
    onError: notifyError,
  })
}

/**
 * 勾选完成：完成是可逆操作（AGENTS 第 19 条）——立即生效，toast 里提供「撤销」= 重新打开（PATCH {done:false}）。
 */
export function useCompleteTask(): { complete: (t: Pick<TaskItem, "id" | "title">) => void; pendingId: string | null } {
  const update = useUpdateTask()
  // 用 mutateAsync 而不是 mutate 的回调：完成后列表 / 侧栏会刷新重渲染，mutate 的单次回调可能被丢掉，撤销 toast 就不出现
  const complete = useCallback(
    (t: Pick<TaskItem, "id" | "title">) =>
      void update
        .mutateAsync({ id: t.id, done: true })
        .then(() =>
          toast.success(taskDoneText(t.title), {
            duration: UNDO_DURATION_MS,
            action: {
              label: UNDO_LABEL,
              onClick: () =>
                void update
                  .mutateAsync({ id: t.id, done: false })
                  .then(() => toast.success("已撤销，任务重新打开"))
                  .catch(() => undefined),
            },
          }),
        )
        .catch(() => undefined), // 错误提示由 useUpdateTask 的 onError 统一处理
    [update],
  )
  return { complete, pendingId: update.isPending ? (update.variables?.id ?? null) : null }
}
