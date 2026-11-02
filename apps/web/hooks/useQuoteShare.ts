"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { notifyError } from "@/hooks/notify"
import { activityKeys } from "@/hooks/useDashboard"
import { quoteKeys } from "@/hooks/useQuotes"
import { api } from "@/lib/api"
import type { ClientCost } from "@/lib/client-costs"
import type { QuoteStatus } from "@/types/api"

/** GET / POST /api/quotes/{id}/share（契约 §35） */
export interface QuoteShare {
  token: string
  /** 前端路由 /share/q/{token}，拼上当前域名就是发给客户的链接 */
  path: string
  expires_at: string
  view_count: number
  last_viewed_at: string | null
  created_at: string
}

export interface PublicQuoteLine {
  name: string
  unit: string
  qty: number
  /** 单位：分 */
  unit_price: number
  /** 单位：分 */
  subtotal_price: number
  category: string
}

/** GET /api/public/quotes/{token}：客户看到的报价，不含成本、毛利、提成 */
export interface PublicQuote {
  code: string
  status: QuoteStatus
  customer_name: string | null
  opportunity_name: string | null
  tier_name: string
  owner_name: string | null
  created_at: string
  valid_until: string
  items: PublicQuoteLine[]
  list_price: number
  discount_rate: number
  total_price: number
  client_costs?: ClientCost[]
  scope?: {
    platforms?: string[]
    modules?: string[]
    team_size?: number | null
    /** 需求里有但这一档不含的端、功能（经济版砍掉的、销售删掉的） */
    excluded_platforms?: string[]
    excluded_modules?: string[]
  } | null
  terms?: string[]
}

const shareKey = (id: string) => [...quoteKeys.detail(id), "share"] as const

export function useQuoteShare(quoteId: string, enabled = true) {
  return useQuery({
    queryKey: shareKey(quoteId),
    queryFn: ({ signal }) => api.get<QuoteShare | null>(`/api/quotes/${quoteId}/share`, undefined, signal),
    enabled: enabled && Boolean(quoteId),
  })
}

/** 生成链接（已审批的报价同时记为「已发送客户」）/ 撤销链接 */
export function useQuoteShareActions(quoteId: string) {
  const qc = useQueryClient()
  const refresh = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: quoteKeys.all }),
      qc.invalidateQueries({ queryKey: activityKeys.all }),
      qc.invalidateQueries({ queryKey: ["tasks"] }),
    ])
  const create = useMutation({
    mutationFn: () => api.post<QuoteShare>(`/api/quotes/${quoteId}/share`),
    onSuccess: (share) => {
      qc.setQueryData(shareKey(quoteId), share)
      void refresh()
    },
    onError: notifyError,
  })
  const revoke = useMutation({
    mutationFn: () => api.delete<null>(`/api/quotes/${quoteId}/share`),
    onSuccess: () => {
      qc.setQueryData(shareKey(quoteId), null)
      void refresh()
    },
    onError: notifyError,
  })
  return { create, revoke }
}

/** 客户打开分享页：不需要登录 */
export function usePublicQuote(token: string) {
  return useQuery({
    queryKey: ["public-quote", token],
    queryFn: ({ signal }) => api.get<PublicQuote>(`/api/public/quotes/${encodeURIComponent(token)}`, undefined, signal),
    enabled: Boolean(token),
  })
}
