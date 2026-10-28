"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"
import type { ThreadMessages, ThreadPage } from "@/lib/thread-history"

export const threadKeys = {
  list: ["agent", "threads"] as const,
  messages: (id: string) => ["agent", "threads", id, "messages"] as const,
}

/** GET /api/agent/threads?limit=30（只返回当前用户自己的会话，按更新时间倒序） */
export function useAgentThreads(limit = 30) {
  return useQuery({
    queryKey: threadKeys.list,
    queryFn: ({ signal }) => api.get<ThreadPage>("/api/agent/threads", { limit }, signal),
    staleTime: 30_000,
  })
}

/** GET /api/agent/threads/{id}/messages */
export function fetchThreadMessages(id: string, signal?: AbortSignal): Promise<ThreadMessages> {
  return api.get<ThreadMessages>(`/api/agent/threads/${encodeURIComponent(id)}/messages`, undefined, signal)
}

/** PATCH /api/agent/threads/{id}：会话改名 */
export function useRenameThread() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      api.patch(`/api/agent/threads/${encodeURIComponent(id)}`, { title }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: threadKeys.list }),
    onError: notifyError,
  })
}

/** DELETE /api/agent/threads/{id}：删除会话（含对话记录） */
export function useDeleteThread() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/agent/threads/${encodeURIComponent(id)}`),
    onSuccess: () => {
      toast.success("会话已删除")
      void qc.invalidateQueries({ queryKey: threadKeys.list })
    },
    onError: notifyError,
  })
}
