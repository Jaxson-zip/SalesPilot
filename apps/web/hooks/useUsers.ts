"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type { Paged, UserItem } from "@/types/api"

export const userKeys = {
  list: (scope: "team" | "all", includeInactive = false) => ["users", scope, includeInactive] as const,
}

/** GET /api/users?scope=team（v3 §11）：本团队成员，用于报销参与人、转移负责人；按人交接时带上已停用的成员 */
export function useTeamUsers(enabled = true, scope: "team" | "all" = "team", includeInactive = false) {
  return useQuery({
    queryKey: userKeys.list(scope, includeInactive),
    queryFn: ({ signal }) =>
      api.get<Paged<UserItem>>("/api/users", { scope, include_inactive: includeInactive || undefined }, signal),
    staleTime: 5 * 60_000,
    enabled,
  })
}
