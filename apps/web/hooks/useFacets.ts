"use client"

import { useQuery } from "@tanstack/react-query"

import { api, type Query } from "@/lib/api"
import type { FilterOption } from "@/lib/list-view"

export type FacetEntity = "customers" | "quotes" | "contracts"

/** GET /api/{entity}/facets：当前范围内的筛选项（行业、负责人、客户、行业包） */
export function useFacets(entity: FacetEntity, query: Query, enabled = true) {
  return useQuery({
    queryKey: [entity, "facets", query] as const,
    queryFn: ({ signal }) => api.get<Record<string, FilterOption[]>>(`/api/${entity}/facets`, query, signal),
    staleTime: 60_000,
    enabled,
  })
}
