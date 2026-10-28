"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { dashboardKeys } from "@/hooks/useDashboard"
import { api } from "@/lib/api"
import { formatFen } from "@/lib/format"
import type {
  ContractItem,
  ContractList,
  ContractListParams,
  PaymentIn,
  PaymentPlanUpdate,
  PaymentPlanView,
} from "@/types/api"

export const contractKeys = {
  all: ["contracts"] as const,
  list: (p: ContractListParams) => ["contracts", "list", p] as const,
  detail: (id: string) => ["contracts", "detail", id] as const,
  plan: (id: string) => ["contracts", "plan", id] as const,
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

/** GET /api/contracts/{id}/payment-plan（B9） */
export function usePaymentPlan(id: string | null) {
  return useQuery({
    queryKey: contractKeys.plan(id ?? ""),
    queryFn: ({ signal }) => api.get<PaymentPlanView>(`/api/contracts/${id}/payment-plan`, undefined, signal),
    enabled: Boolean(id),
  })
}

/** PUT /api/contracts/{id}/payment-plan（仅合同负责人；合计不等于合同金额时 42201） */
export function useSavePaymentPlan(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: PaymentPlanUpdate) => api.put<PaymentPlanView>(`/api/contracts/${id}/payment-plan`, body),
    onSuccess: (plan) => {
      qc.setQueryData(contractKeys.plan(id), plan)
      toast.success("回款计划已保存", { description: plan.code })
      void qc.invalidateQueries({ queryKey: contractKeys.all })
    },
    onError: notifyError,
  })
}
