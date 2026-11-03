"use client"

import { useQuery } from "@tanstack/react-query"

import { useSession } from "@/components/shell/SessionProvider"
import { api } from "@/lib/api"
import type { Templates } from "@/types/api"

/**
 * GET /api/templates：报销 / 跟进 / 下一步 / 输单原因 / 报价条款 / AI 示例问题（按角色）。很少变化，缓存 10 分钟。
 * fresh：每次打开都重新取。AI 示例问题按本人的客户和商机填写，商机输单 / 删除后要马上换掉
 */
export function useTemplates({ fresh = false }: { fresh?: boolean } = {}) {
  const { role } = useSession()
  return useQuery({
    queryKey: ["templates", role],
    queryFn: ({ signal }) => api.get<Templates>("/api/templates", undefined, signal),
    staleTime: 10 * 60_000,
    refetchOnMount: fresh ? "always" : true,
  })
}
