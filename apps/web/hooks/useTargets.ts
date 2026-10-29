"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"
import type { TargetBoard, TargetUpdate } from "@/lib/targets"

export const targetKeys = { all: ["targets"] as const, month: (m: string) => ["targets", m] as const }

/** GET /api/targets?month=：month 为空取本月 */
export function useTargets(month: string) {
  return useQuery({
    queryKey: targetKeys.month(month),
    queryFn: ({ signal }) => api.get<TargetBoard>("/api/targets", month ? { month } : undefined, signal),
    placeholderData: keepPreviousData,
  })
}

/** PUT /api/targets/{month}（仅主管） */
export function useUpdateTargets(month: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TargetUpdate) => api.put<TargetBoard>(`/api/targets/${month}`, body),
    onSuccess: (b) => {
      qc.setQueryData(targetKeys.month(b.month), b)
      toast.success("目标已保存")
      void qc.invalidateQueries({ queryKey: ["dashboard"] })
    },
    onError: notifyError,
  })
}
