"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { activityKeys, dashboardKeys } from "@/hooks/useDashboard"
import { api } from "@/lib/api"
import { STAGE_META } from "@/lib/labels"
import { fetchAllPaged } from "@/lib/paging"
import { applyStageChange } from "@/lib/pipeline"
import type {
  DataView,
  OpportunityCreate,
  OpportunityDetail,
  OpportunityItem,
  OpportunityListParams,
  OpportunityUpdate,
  Paged,
  PipelineSummary,
  StageChange,
} from "@/types/api"

export const opportunityKeys = {
  all: ["opportunities"] as const,
  lists: ["opportunities", "list"] as const,
  list: (p: OpportunityListParams) => ["opportunities", "list", p] as const,
  detail: (id: string) => ["opportunities", "detail", id] as const,
  summary: (view: DataView) => ["pipeline", "summary", view] as const,
}

/** 看板最多显示的商机数（超过时提示用列表筛选） */
export const BOARD_MAX = 1000

/**
 * 看板：逐页取全部商机（每页 100 条，最多 BOARD_MAX 条），在前端按阶段分组、筛选。
 * 缓存键在 opportunityKeys.lists 下，拖拽改阶段的乐观更新同样生效。
 */
export function useBoardOpportunities(view: DataView) {
  return useQuery({
    queryKey: [...opportunityKeys.lists, "board", view] as const,
    queryFn: ({ signal }) => fetchAllPaged<OpportunityItem>("/api/opportunities", { view }, BOARD_MAX, signal),
    placeholderData: keepPreviousData,
  })
}

/** GET /api/opportunities（客户详情、报销关联等按客户取少量） */
export function useOpportunities(params: OpportunityListParams, enabled = true) {
  return useQuery({
    queryKey: opportunityKeys.list(params),
    queryFn: ({ signal }) =>
      api.get<Paged<OpportunityItem>>(
        "/api/opportunities",
        {
          view: params.view,
          stage: params.stage,
          customer_id: params.customer_id,
          q: params.q,
          page: params.page ?? 1,
          page_size: params.page_size ?? 100,
        },
        signal,
      ),
    placeholderData: keepPreviousData,
    enabled,
  })
}

/** GET /api/opportunities/{id} */
export function useOpportunity(id: string | null) {
  return useQuery({
    queryKey: opportunityKeys.detail(id ?? ""),
    queryFn: ({ signal }) => api.get<OpportunityDetail>(`/api/opportunities/${id}`, undefined, signal),
    enabled: Boolean(id),
  })
}

/** GET /api/pipeline/summary?view= */
export function usePipelineSummary(view: DataView) {
  return useQuery({
    queryKey: opportunityKeys.summary(view),
    queryFn: ({ signal }) => api.get<PipelineSummary>("/api/pipeline/summary", { view }, signal),
  })
}

function invalidatePipeline(qc: QueryClient): Promise<unknown> {
  return Promise.all([
    qc.invalidateQueries({ queryKey: opportunityKeys.all }),
    qc.invalidateQueries({ queryKey: ["pipeline"] }),
    qc.invalidateQueries({ queryKey: dashboardKeys.all }),
    qc.invalidateQueries({ queryKey: activityKeys.all }),
  ])
}

/** POST /api/opportunities */
export function useCreateOpportunity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: OpportunityCreate) => api.post<OpportunityItem>("/api/opportunities", body),
    onSuccess: (opp) => {
      toast.success("商机已创建", { description: `${opp.name} · ${STAGE_META.lead.label}` })
      void invalidatePipeline(qc)
    },
    onError: notifyError,
  })
}

/** PATCH /api/opportunities/{id}（U10 行内编辑） */
export function useUpdateOpportunity(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: OpportunityUpdate) => api.patch<OpportunityItem>(`/api/opportunities/${id}`, body),
    onSuccess: () => {
      toast.success("已保存")
      void Promise.all([
        invalidatePipeline(qc),
        qc.invalidateQueries({ queryKey: opportunityKeys.detail(id) }),
        qc.invalidateQueries({ queryKey: ["customers"] }),
      ])
    },
    onError: notifyError,
  })
}

type StageVars = StageChange & { id: string }
type Snapshot = [readonly unknown[], unknown][]

/** PATCH /api/opportunities/{id}/stage —— 乐观更新所有商机列表缓存，失败回滚并提示；成功提示（含撤销）由 useStageMove 负责 */
export function useChangeStage() {
  const qc = useQueryClient()
  return useMutation<OpportunityItem, unknown, StageVars, { snapshot: Snapshot }>({
    mutationFn: ({ id, ...body }) => api.patch<OpportunityItem>(`/api/opportunities/${id}/stage`, body),
    onMutate: async ({ id, stage }) => {
      await qc.cancelQueries({ queryKey: opportunityKeys.lists })
      await qc.cancelQueries({ queryKey: opportunityKeys.detail(id) })
      const snapshot: Snapshot = [
        ...qc.getQueriesData<Paged<OpportunityItem>>({ queryKey: opportunityKeys.lists }),
        [opportunityKeys.detail(id), qc.getQueryData(opportunityKeys.detail(id))],
      ]
      qc.setQueriesData<Paged<OpportunityItem>>({ queryKey: opportunityKeys.lists }, (old) =>
        applyStageChange(old, id, stage),
      )
      qc.setQueryData<OpportunityDetail>(opportunityKeys.detail(id), (old) => (old ? { ...old, stage } : old))
      return { snapshot }
    },
    onError: (err, _vars, ctx) => {
      ctx?.snapshot.forEach(([key, data]) => qc.setQueryData(key, data))
      notifyError(err)
    },
    onSettled: (_data, _err, vars) =>
      Promise.all([
        invalidatePipeline(qc),
        // 按报价成交会生成合同
        vars.quote_id ? qc.invalidateQueries({ queryKey: ["quotes"] }) : null,
        vars.quote_id ? qc.invalidateQueries({ queryKey: ["contracts"] }) : null,
      ]),
  })
}
