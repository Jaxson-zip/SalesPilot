"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type { Customer, CustomerListParams, Paged } from "@/types/api"

export const customerKeys = {
  all: ["customers"] as const,
  list: (p: CustomerListParams) => ["customers", "list", p] as const,
}

/** GET /api/customers?view=&page=&page_size= */
export function useCustomers(params: CustomerListParams) {
  return useQuery({
    queryKey: customerKeys.list(params),
    queryFn: ({ signal }) =>
      api.get<Paged<Customer>>(
        "/api/customers",
        { view: params.view, page: params.page, page_size: params.page_size },
        signal,
      ),
    placeholderData: keepPreviousData,
  })
}
