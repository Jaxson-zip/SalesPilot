"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"

export type MeddicKey =
  "metrics" | "economic_buyer" | "decision_criteria" | "decision_process" | "identify_pain" | "champion"
export type MeddicStatus = "confirmed" | "partial" | "missing"

export interface MeddicItem {
  key: MeddicKey
  label: string
  hint: string
  status: MeddicStatus
  evidence?: string | null
  updated_at?: string | null
  updated_by?: string | null
  questions: string[]
  required: boolean
  risk: boolean
}

export interface MeddicOut {
  opportunity_id: string
  stage: string
  score: number
  items: MeddicItem[]
  gaps: string[]
  risks: string[]
}

export interface MeddicSuggestion {
  key: MeddicKey
  status: MeddicStatus
  evidence?: string | null
}

export interface MeddicAssessOut {
  source: "ai" | "rule"
  summary: string
  items: MeddicSuggestion[]
}

export interface MeddicPatch {
  status: MeddicStatus
  evidence?: string | null
}

const key = (id: string) => ["meddic", id] as const

/** GET /api/opportunities/{id}/meddic */
export function useMeddic(id: string | null) {
  return useQuery({
    queryKey: key(id ?? ""),
    queryFn: ({ signal }) => api.get<MeddicOut>(`/api/opportunities/${id}/meddic`, undefined, signal),
    enabled: Boolean(id),
  })
}

/** PUT /api/opportunities/{id}/meddic（只传要改的项） */
export function useSaveMeddic(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (items: Partial<Record<MeddicKey, MeddicPatch>>) =>
      api.put<MeddicOut>(`/api/opportunities/${id}/meddic`, { items }),
    onSuccess: (data) => {
      qc.setQueryData(key(id), data)
      void qc.invalidateQueries({ queryKey: ["opportunities"] })
    },
    onError: notifyError,
  })
}

/** POST /api/opportunities/{id}/meddic/assess：AI 建议（不保存） */
export function useAssessMeddic(id: string) {
  return useMutation({
    mutationFn: () => api.post<MeddicAssessOut>(`/api/opportunities/${id}/meddic/assess`),
    onError: notifyError,
    onSuccess: (r) => {
      if (r.items.length === 0) toast("跟进记录里还看不到相关信息，先多了解客户再评估")
    },
  })
}
