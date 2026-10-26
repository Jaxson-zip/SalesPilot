"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type { Customer, CustomerDetail, CustomerListParams, Paged } from "@/types/api"

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
