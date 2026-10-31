"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"

/** 下一步建议（core suggestion_service，规则计算）：每条带一句交给 AI 的话 */
export interface DealSuggestion {
  kind:
    | "overdue_payment"
    | "quote_unsent"
    | "stale"
    | "task_overdue"
    | "no_next_step"
    | "meddic_gap"
    | "no_quote"
    | "competitor"
  level: "warn" | "info"
  title: string
  detail?: string | null
  prompt: string
  opportunity_id: string
  opportunity_name: string
}

// 挂在详情的缓存键下：商机 / 客户详情失效（改阶段、记跟进、建任务）时建议跟着刷新
export function useOpportunitySuggestions(id: string | null) {
  return useQuery({
    queryKey: ["opportunities", "detail", id ?? "", "suggestions"],
    queryFn: ({ signal }) => api.get<DealSuggestion[]>(`/api/opportunities/${id}/suggestions`, undefined, signal),
    enabled: Boolean(id),
  })
}

export function useCustomerSuggestions(id: string) {
  return useQuery({
    queryKey: ["customers", "detail", id, "suggestions"],
    queryFn: ({ signal }) => api.get<DealSuggestion[]>(`/api/customers/${id}/suggestions`, undefined, signal),
    enabled: Boolean(id),
  })
}
