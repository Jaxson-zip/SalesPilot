"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"
import { markReadLocally } from "@/lib/notifications"
import type { NotificationList } from "@/types/api"

export const notificationKeys = {
  all: ["notifications"] as const,
  list: ["notifications", "list"] as const,
}

const REFRESH_MS = 60_000

/** GET /api/notifications?limit=20（v3 §15）：每 60 秒刷新一次 */
export function useNotifications() {
  return useQuery({
    queryKey: notificationKeys.list,
    queryFn: ({ signal }) => api.get<NotificationList>("/api/notifications", { limit: 20 }, signal),
    refetchInterval: REFRESH_MS,
    retry: false,
  })
}

/** POST /api/notifications/read：传 ids 标记这些；不传表示全部已读。本地先乐观更新 */
export function useMarkNotificationsRead() {
  const qc = useQueryClient()
  return useMutation<unknown, unknown, string[] | undefined, { prev: NotificationList | undefined }>({
    mutationFn: (ids) => api.post<unknown>("/api/notifications/read", ids ? { ids } : {}),
    onMutate: async (ids) => {
      await qc.cancelQueries({ queryKey: notificationKeys.list })
      const prev = qc.getQueryData<NotificationList>(notificationKeys.list)
      if (prev) {
        const { items, changed } = markReadLocally(prev.items, ids)
        qc.setQueryData<NotificationList>(notificationKeys.list, {
          ...prev,
          items,
          unread: ids ? Math.max(0, prev.unread - changed) : 0,
        })
      }
      return { prev }
    },
    onError: (err, _ids, ctx) => {
      if (ctx?.prev) qc.setQueryData(notificationKeys.list, ctx.prev)
      notifyError(err)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: notificationKeys.all }),
  })
}
