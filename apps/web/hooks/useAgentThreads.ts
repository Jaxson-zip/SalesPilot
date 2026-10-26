"use client"

import { useQuery } from "@tanstack/react-query"

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
