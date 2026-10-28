"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"

export interface Objection {
  say: string
  respond: string
}

export interface CompetitorInput {
  name: string
  aliases: string[]
  summary?: string | null
  strengths: string[]
  weaknesses: string[]
  win_tactics: string[]
  objections: Objection[]
}

export interface CompetitorStats {
  open: number
  won: number
  lost: number
  lost_reasons: string[]
}

export interface Competitor extends CompetitorInput {
  id: string
  updated_by?: string | null
  stats: CompetitorStats
}

const keys = {
  all: ["competitors"] as const,
  list: (q: string) => ["competitors", "list", q] as const,
  opp: (id: string) => ["competitors", "opp", id] as const,
}

/** GET /api/competitors?q=（q 匹配名称、别名、弱点、打法和常见说法） */
export function useCompetitors(q = "") {
  return useQuery({
    queryKey: keys.list(q),
    queryFn: ({ signal }) => api.get<Competitor[]>("/api/competitors", q ? { q } : undefined, signal),
    placeholderData: keepPreviousData,
  })
}

/** 新建 / 修改 / 删除战卡（管理员） */
export function useSaveCompetitor() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: CompetitorInput }) =>
      id ? api.put<Competitor>(`/api/competitors/${id}`, body) : api.post<Competitor>("/api/competitors", body),
    onSuccess: () => {
      toast.success("战卡已保存")
      void qc.invalidateQueries({ queryKey: keys.all })
    },
    onError: notifyError,
  })
}

export function useDeleteCompetitor() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete<null>(`/api/competitors/${id}`),
    onSuccess: () => {
      toast.success("战卡已删除")
      void qc.invalidateQueries({ queryKey: keys.all })
    },
    onError: notifyError,
  })
}

/** GET /api/opportunities/{id}/competitors */
export function useOpportunityCompetitors(id: string) {
  return useQuery({
    queryKey: keys.opp(id),
    queryFn: ({ signal }) => api.get<Competitor[]>(`/api/opportunities/${id}/competitors`, undefined, signal),
  })
}

/** PUT /api/opportunities/{id}/competitors（覆盖式，仅负责人） */
export function useSetOpportunityCompetitors(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ids: string[]) => api.put<Competitor[]>(`/api/opportunities/${id}/competitors`, { ids }),
    onSuccess: (data) => {
      qc.setQueryData(keys.opp(id), data)
      void qc.invalidateQueries({ queryKey: ["competitors", "list"] })
    },
    onError: notifyError,
  })
}
