"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { activityKeys, dashboardKeys } from "@/hooks/useDashboard"
import { opportunityKeys } from "@/hooks/useOpportunities"
import { api } from "@/lib/api"
import { QUOTE_ACTIONS, submitResultText } from "@/lib/quote-actions"
import type { Paged, QuoteAction, QuoteDetail, QuoteItem, QuoteListParams } from "@/types/api"

export const quoteKeys = {
  all: ["quotes"] as const,
  list: (p: QuoteListParams) => ["quotes", "list", p] as const,
  detail: (id: string) => ["quotes", "detail", id] as const,
}

/** GET /api/quotes?view=&status=&opportunity_id=&q= */
export function useQuotes(params: QuoteListParams, enabled = true) {
  return useQuery({
    queryKey: quoteKeys.list(params),
    queryFn: ({ signal }) =>
      api.get<Paged<QuoteItem>>(
        "/api/quotes",
        {
          view: params.view,
          status: params.status,
          opportunity_id: params.opportunity_id,
          customer_id: params.customer_id,
          q: params.q,
          page: params.page ?? 1,
          page_size: params.page_size ?? 20,
        },
        signal,
      ),
    placeholderData: keepPreviousData,
    enabled,
  })
}

/** GET /api/quotes/{id}（含明细和审批记录） */
export function useQuote(id: string) {
  return useQuery({
    queryKey: quoteKeys.detail(id),
    queryFn: ({ signal }) => api.get<QuoteDetail>(`/api/quotes/${id}`, undefined, signal),
    enabled: Boolean(id),
  })
}

/** POST /api/quotes/{id}/submit|send|accept|reject */
export function useQuoteAction(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (action: QuoteAction) => api.post<QuoteDetail>(`/api/quotes/${id}/${action}`),
    onSuccess: (quote, action) => {
      const text = action === "submit" && quote?.status ? submitResultText(quote.status) : QUOTE_ACTIONS[action].done
      toast.success(text, { description: quote?.code })
      if (quote?.id) qc.setQueryData(quoteKeys.detail(id), quote)
      void Promise.all([
        qc.invalidateQueries({ queryKey: quoteKeys.all }),
        qc.invalidateQueries({ queryKey: dashboardKeys.all }),
        qc.invalidateQueries({ queryKey: activityKeys.all }),
        // accept 会生成合同并把商机改为赢单
        qc.invalidateQueries({ queryKey: ["contracts"] }),
        qc.invalidateQueries({ queryKey: opportunityKeys.all }),
        qc.invalidateQueries({ queryKey: ["approvals"] }),
      ])
    },
    onError: notifyError,
  })
}
