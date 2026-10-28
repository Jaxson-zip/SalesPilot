"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type { Paged } from "@/types/api"

export interface AuditItem {
  id: string
  created_at: string
  user_name: string | null
  role: string | null
  action: string
  label: string
  source: "web" | "agent" | string
  target_id: string | null
  target_name?: string | null
  status: number
  ok: boolean
  detail: string | null
  ip: string | null
}

export interface AuditParams {
  q?: string
  action?: string
  result?: "ok" | "failed"
  source?: "web" | "agent"
  page: number
  page_size: number
}

/** GET /api/audit-logs：管理员看全公司，主管看本团队 */
export function useAuditLogs(params: AuditParams) {
  return useQuery({
    queryKey: ["audit-logs", params],
    queryFn: ({ signal }) =>
      api.get<Paged<AuditItem>>(
        "/api/audit-logs",
        {
          q: params.q || undefined,
          action: params.action || undefined,
          result: params.result,
          source: params.source,
          page: params.page,
          page_size: params.page_size,
        },
        signal,
      ),
    placeholderData: keepPreviousData,
  })
}
