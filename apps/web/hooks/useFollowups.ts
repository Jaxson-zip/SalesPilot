"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { activityKeys, dashboardKeys } from "@/hooks/useDashboard"
import { api } from "@/lib/api"
import type { ContactIn, ContactItem, ContactUpdate, FollowupCreate, FollowupItem, Paged } from "@/types/api"

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

function useContactInvalidate(customerId: string) {
  const qc = useQueryClient()
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: followupKeys.contacts(customerId) }),
      qc.invalidateQueries({ queryKey: activityKeys.all }),
    ])
}

/** 新建（id 为空）或修改联系人：POST / PATCH /api/customers/{id}/contacts[/{contactId}] */
export function useSaveContact(customerId: string) {
  const invalidate = useContactInvalidate(customerId)
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: ContactIn | ContactUpdate }) =>
      id
        ? api.patch<ContactItem>(`/api/customers/${customerId}/contacts/${id}`, body)
        : api.post<ContactItem>(`/api/customers/${customerId}/contacts`, body),
    onSuccess: (c, { id }) => {
      toast.success(id ? "联系人已更新" : "联系人已添加", { description: c.name })
      void invalidate()
    },
    onError: notifyError,
  })
}

/** DELETE /api/customers/{id}/contacts/{contactId} */
export function useDeleteContact(customerId: string) {
  const invalidate = useContactInvalidate(customerId)
  return useMutation({
    mutationFn: (contact: ContactItem) => api.delete<null>(`/api/customers/${customerId}/contacts/${contact.id}`),
    onSuccess: (_, contact) => {
      toast.success("联系人已删除", { description: contact.name })
      void invalidate()
    },
    onError: notifyError,
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
