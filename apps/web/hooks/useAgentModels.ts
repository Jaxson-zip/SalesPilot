"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type { ChatModels } from "@/types/api"

/** GET /api/agent/models：对话可选的模型和可用状态（配了 Key 才可用），1 分钟内不重复请求 */
export function useAgentModels() {
  return useQuery({
    queryKey: ["agent", "models"],
    queryFn: ({ signal }) => api.get<ChatModels>("/api/agent/models", undefined, signal),
    staleTime: 60_000,
    retry: false,
  })
}
