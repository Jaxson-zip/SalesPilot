"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { dashboardKeys } from "@/hooks/useDashboard"
import { api } from "@/lib/api"
import { formatFen } from "@/lib/format"
import type { ContractItem, ContractList, ContractListParams, PaymentIn } from "@/types/api"

export const contractKeys = {
  all: ["contracts"] as const,
  list: (p: ContractListParams) => ["contracts", "list", p] as const,
  detail: (id: string) => ["contracts", "detail", id] as const,
}

/** GET /api/contracts?view=&status=（data 额外带 summary） */
export function useContracts(params: ContractListParams) {
  return useQuery({
    queryKey: contractKeys.list(params),
    queryFn: ({ signal }) =>
      api.get<ContractList>(
        "/api/contracts",
        { view: params.view, status: params.status, page: params.page ?? 1, page_size: params.page_size ?? 20 },
        signal,
      ),
    placeholderData: keepPreviousData,
  })
}

/** POST /api/contracts/{id}/payments（仅 manager / admin，否则 40301） */
export function useRegisterPayment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: PaymentIn & { id: string }) =>
      api.post<ContractItem>(`/api/contracts/${id}/payments`, body),
    onSuccess: (contract, vars) => {
      toast.success("回款已登记", { description: `${contract?.code ?? ""} · ${formatFen(vars.amount)}` })
      void Promise.all([
        qc.invalidateQueries({ queryKey: contractKeys.all }),
        qc.invalidateQueries({ queryKey: dashboardKeys.all }),
      ])
    },
    onError: notifyError,
  })
}
