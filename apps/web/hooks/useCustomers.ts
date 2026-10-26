"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { activityKeys } from "@/hooks/useDashboard"
import { api } from "@/lib/api"
import type { Customer, CustomerCreate, CustomerDetail, CustomerListParams, Paged } from "@/types/api"

export const customerKeys = {
  all: ["customers"] as const,
  list: (p: CustomerListParams) => ["customers", "list", p] as const,
  detail: (id: string) => ["customers", "detail", id] as const,
}

/** GET /api/customers?view=&page=&page_size= */
export function useCustomers(params: CustomerListParams, enabled = true) {
  return useQuery({
    queryKey: customerKeys.list(params),
    queryFn: ({ signal }) =>
      api.get<Paged<Customer>>(
        "/api/customers",
        { view: params.view, page: params.page, page_size: params.page_size },
        signal,
      ),
    placeholderData: keepPreviousData,
    enabled,
  })
}

/** GET /api/customers/{id} */
export function useCustomer(id: string) {
  return useQuery({
    queryKey: customerKeys.detail(id),
    queryFn: ({ signal }) => api.get<CustomerDetail>(`/api/customers/${id}`, undefined, signal),
    enabled: Boolean(id),
  })
}

/** POST /api/customers：成功后刷新客户列表并写入详情缓存 */
export function useCreateCustomer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CustomerCreate) => api.post<CustomerDetail>("/api/customers", body),
    onSuccess: (c) => {
      qc.setQueryData(customerKeys.detail(c.id), c)
      toast.success("客户已创建", { description: c.name })
      void qc.invalidateQueries({ queryKey: customerKeys.all })
      void qc.invalidateQueries({ queryKey: activityKeys.all })
    },
    onError: notifyError,
  })
}
