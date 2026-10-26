"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { activityKeys, dashboardKeys } from "@/hooks/useDashboard"
import { api } from "@/lib/api"
import type { ApprovalDecideIn, ApprovalItem, ApprovalTab, Paged } from "@/types/api"

export const approvalKeys = {
  all: ["approvals"] as const,
  list: (status: ApprovalTab) => ["approvals", "list", status] as const,
}

/** GET /api/approvals?status=pending|done（仅 manager，其他角色 40301） */
export function useApprovals(status: ApprovalTab, enabled = true) {
  return useQuery({
    queryKey: approvalKeys.list(status),
    queryFn: ({ signal }) => api.get<Paged<ApprovalItem>>("/api/approvals", { status, page: 1, page_size: 50 }, signal),
    placeholderData: keepPreviousData,
    enabled,
  })
}

/** POST /api/approvals/{id}/decide */
export function useDecideApproval() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: ApprovalDecideIn & { id: string }) =>
      api.post<ApprovalItem>(`/api/approvals/${id}/decide`, body),
    onSuccess: (_res, vars) => {
      toast.success(vars.decision === "approve" ? "已通过审批" : "已驳回")
      void Promise.all([
        qc.invalidateQueries({ queryKey: approvalKeys.all }),
        qc.invalidateQueries({ queryKey: dashboardKeys.all }),
        qc.invalidateQueries({ queryKey: activityKeys.all }),
        qc.invalidateQueries({ queryKey: ["quotes"] }),
        qc.invalidateQueries({ queryKey: ["expenses"] }),
      ])
    },
    onError: notifyError,
  })
}
