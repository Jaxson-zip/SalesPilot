"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { activityKeys, dashboardKeys } from "@/hooks/useDashboard"
import { api } from "@/lib/api"
import type { ContactItem, FollowupCreate, FollowupItem, Paged } from "@/types/api"

export const followupKeys = {
  list: (customerId: string) => ["customers", customerId, "followups"] as const,
  contacts: (customerId: string) => ["customers", customerId, "contacts"] as const,
}

function toList<T>(data: Paged<T> | T[]): T[] {
  return Array.isArray(data) ? data : data.items
}

/** GET /api/customers/{id}/followups?limit= */
export function useFollowups(customerId: string, limit = 50) {
  return useQuery({
    queryKey: followupKeys.list(customerId),
    queryFn: async ({ signal }) =>
      toList(
        await api.get<Paged<FollowupItem> | FollowupItem[]>(
          `/api/customers/${customerId}/followups`,
          { limit },
          signal,
        ),
      ),
    enabled: Boolean(customerId),
  })
}

/** GET /api/customers/{id}/contacts */
export function useContacts(customerId: string) {
  return useQuery({
    queryKey: followupKeys.contacts(customerId),
    queryFn: async ({ signal }) =>
      toList(
        await api.get<Paged<ContactItem> | ContactItem[]>(`/api/customers/${customerId}/contacts`, undefined, signal),
      ),
    enabled: Boolean(customerId),
  })
}

/** POST /api/customers/{id}/followups */
export function useCreateFollowup(customerId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: FollowupCreate) => api.post<FollowupItem>(`/api/customers/${customerId}/followups`, body),
    onSuccess: () => {
      toast.success("跟进已保存")
      void Promise.all([
        qc.invalidateQueries({ queryKey: followupKeys.list(customerId) }),
        qc.invalidateQueries({ queryKey: activityKeys.all }),
        qc.invalidateQueries({ queryKey: dashboardKeys.all }),
        qc.invalidateQueries({ queryKey: ["customers"] }),
      ])
    },
    onError: notifyError,
  })
}
