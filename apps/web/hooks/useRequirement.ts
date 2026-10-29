"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type { Requirement } from "@/lib/requirement-card"

/** 商机上保存的需求清单（GET /api/opportunities/{id}/requirement；还没出过方案时为 null） */
export interface OpportunityRequirement {
  pack: string
  data: Requirement
  confirmed: boolean
  /** 分 */
  price_low?: number | null
  price_high?: number | null
  questions: string[]
  updated_at: string
  updated_by?: string | null
}

export const requirementKey = (id: string) => ["opportunities", id, "requirement"] as const

export function useOpportunityRequirement(id: string | null) {
  return useQuery({
    queryKey: requirementKey(id ?? ""),
    queryFn: ({ signal }) =>
      api.get<OpportunityRequirement | null>(`/api/opportunities/${id}/requirement`, undefined, signal),
    enabled: Boolean(id),
  })
}
