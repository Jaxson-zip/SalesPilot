"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type { Paged, UserItem } from "@/types/api"

export const userKeys = {
  list: (scope: "team" | "all") => ["users", scope] as const,
}

/** GET /api/users?scope=team（v3 §11）：本团队成员，用于报销参与人、转移负责人 */
export function useTeamUsers(enabled = true, scope: "team" | "all" = "team") {
  return useQuery({
    queryKey: userKeys.list(scope),
    queryFn: ({ signal }) => api.get<Paged<UserItem>>("/api/users", { scope }, signal),
    staleTime: 5 * 60_000,
    enabled,
  })
}
