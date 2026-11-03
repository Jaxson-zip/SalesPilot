"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type { Activity, ActivityListParams, DashboardData, DataView, Paged, TodoItem } from "@/types/api"

export const dashboardKeys = {
  all: ["dashboard"] as const,
  data: (view: DataView) => ["dashboard", view] as const,
  // 放在 dashboard 前缀下：登记回款、审批等已有的 invalidate(dashboardKeys.all) 会一并刷新
  todos: (view: DataView) => ["dashboard", "todos", view] as const,
}

export const activityKeys = {
  all: ["activities"] as const,
  list: (p: ActivityListParams) => ["activities", p] as const,
}

/** GET /api/dashboard?view= */
export function useDashboard(view: DataView) {
  return useQuery({
    queryKey: dashboardKeys.data(view),
    queryFn: ({ signal }) => api.get<DashboardData>("/api/dashboard", { view }, signal),
  })
}

/** GET /api/dashboard/todos?view=：待办里除任务以外的事项 */
export function useTodoItems(view: DataView) {
  return useQuery({
    queryKey: dashboardKeys.todos(view),
    queryFn: ({ signal }) => api.get<TodoItem[]>("/api/dashboard/todos", { view }, signal),
  })
}

/** 动态列表可能返回 {items,total} 或直接数组，两种都兼容 */
function toList(data: Paged<Activity> | Activity[]): Activity[] {
  return Array.isArray(data) ? data : data.items
}

/** GET /api/activities?view=&subject_type=&subject_id=&limit= */
export function useActivities(params: ActivityListParams, enabled = true) {
  return useQuery({
    queryKey: activityKeys.list(params),
    queryFn: async ({ signal }) =>
      toList(
        await api.get<Paged<Activity> | Activity[]>(
          "/api/activities",
          {
            view: params.view,
            subject_type: params.subject_type,
            subject_id: params.subject_id,
            limit: params.limit ?? 20,
          },
          signal,
        ),
      ),
    // 「加载更多」只改 limit：先保留已显示的条目，不闪骨架屏；换了对象（view / subject）就不保留
    placeholderData: (prev, prevQuery) => {
      const p = prevQuery?.queryKey[1] as ActivityListParams | undefined
      const same =
        p?.view === params.view && p?.subject_type === params.subject_type && p?.subject_id === params.subject_id
      return same ? prev : undefined
    },
    enabled,
  })
}
