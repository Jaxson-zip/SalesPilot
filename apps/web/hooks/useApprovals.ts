"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { activityKeys, dashboardKeys } from "@/hooks/useDashboard"
import { api } from "@/lib/api"
import type { ApprovalDecideIn, ApprovalItem, ApprovalTab, Paged } from "@/types/api"

export const approvalKeys = {
  all: ["approvals"] as const,
  list: (status: ApprovalTab, size: number) => ["approvals", "list", status, size] as const,
}

/** GET /api/approvals?status=pending|done（仅 manager，其他角色 40301）；size 最多 100 */
export function useApprovals(status: ApprovalTab, enabled = true, size = 100) {
  return useQuery({
    queryKey: approvalKeys.list(status, size),
    queryFn: ({ signal }) =>
      api.get<Paged<ApprovalItem>>("/api/approvals", { status, page: 1, page_size: size }, signal),
    placeholderData: keepPreviousData,
    enabled,
  })
}

function invalidateAfterDecide(qc: ReturnType<typeof useQueryClient>) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: approvalKeys.all }),
    qc.invalidateQueries({ queryKey: dashboardKeys.all }),
    qc.invalidateQueries({ queryKey: activityKeys.all }),
    qc.invalidateQueries({ queryKey: ["quotes"] }),
    qc.invalidateQueries({ queryKey: ["expenses"] }),
  ])
}

/** 批量通过 / 驳回：逐条调用 decide（每条都留审计记录），汇总成一条提示 */
export function useBatchDecide() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ ids, ...body }: ApprovalDecideIn & { ids: string[] }) => {
      let ok = 0
      const failed: string[] = []
      for (const id of ids) {
        try {
          await api.post<ApprovalItem>(`/api/approvals/${id}/decide`, body)
          ok += 1
        } catch {
          failed.push(id)
        }
      }
      return { ok, failed }
    },
    onSuccess: ({ ok, failed }, vars) => {
      const verb = vars.decision === "approve" ? "通过" : "驳回"
      if (failed.length) toast.warning(`已${verb} ${ok} 条，${failed.length} 条失败（可能已被处理），请刷新后查看`)
      else toast.success(`已${verb} ${ok} 条`)
      void invalidateAfterDecide(qc)
    },
    onError: notifyError,
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
      void invalidateAfterDecide(qc)
    },
    onError: notifyError,
  })
}
