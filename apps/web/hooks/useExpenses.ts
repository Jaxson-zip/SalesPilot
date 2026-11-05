"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { dashboardKeys } from "@/hooks/useDashboard"
import { api } from "@/lib/api"
import { isExpenseDetailKey } from "@/lib/expense"
import { serverQuery, type ServerListParams } from "@/lib/list-view"
import type {
  AttachmentKind,
  AttachmentOut,
  ExpenseCreate,
  ExpenseDetail,
  ExpenseItem,
  ExpenseListParams,
  ExpensePrecheck,
  Paged,
} from "@/types/api"

export const expenseKeys = {
  all: ["expenses"] as const,
  list: (p: ExpenseListParams) => ["expenses", "list", p] as const,
  detail: (id: string) => ["expenses", "detail", id] as const,
  precheck: (body: ExpenseCreate | null) => ["expenses", "precheck", body] as const,
}

/** GET /api/expenses?view=&status= */
export function useExpenses(params: ExpenseListParams, list?: ServerListParams) {
  return useQuery({
    queryKey: [...expenseKeys.list(params), list],
    queryFn: ({ signal }) =>
      api.get<Paged<ExpenseItem>>(
        "/api/expenses",
        {
          view: params.view,
          status: params.status,
          opportunity_id: params.opportunity_id,
          page: params.page ?? 1,
          page_size: params.page_size ?? 20,
          ...serverQuery(list ?? {}),
        },
        signal,
      ),
    placeholderData: keepPreviousData,
  })
}

/** GET /api/expenses/{id}（含附件、制度校验结果） */
export function useExpense(id: string | null) {
  return useQuery({
    queryKey: expenseKeys.detail(id ?? ""),
    queryFn: ({ signal }) => api.get<ExpenseDetail>(`/api/expenses/${id}`, undefined, signal),
    enabled: Boolean(id),
  })
}

/** POST /api/expenses/precheck —— 不落库的制度校验，表单变化时实时调用（body 由调用方防抖） */
export function useExpensePrecheck(body: ExpenseCreate | null) {
  return useQuery({
    queryKey: expenseKeys.precheck(body),
    queryFn: ({ signal }) => api.post<ExpensePrecheck>("/api/expenses/precheck", body, signal),
    enabled: body !== null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  })
}

/** POST /api/expenses —— 新建草稿 */
export function useCreateExpense() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ExpenseCreate) => api.post<ExpenseDetail>("/api/expenses", body),
    onSuccess: (exp) => {
      qc.setQueryData(expenseKeys.detail(exp.id), exp)
      void qc.invalidateQueries({ queryKey: expenseKeys.all })
    },
    onError: notifyError,
  })
}

/** PUT /api/expenses/{id} —— 修改草稿或被驳回的报销单（整单替换），改完再提交 */
export function useUpdateExpense() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ExpenseCreate }) =>
      api.put<ExpenseDetail>(`/api/expenses/${id}`, body),
    onSuccess: (exp) => {
      qc.setQueryData(expenseKeys.detail(exp.id), exp)
      toast.success("报销单已修改", { description: `${exp.code} · 确认无误后提交` })
      void qc.invalidateQueries({ queryKey: expenseKeys.all })
    },
    onError: notifyError,
  })
}

/** POST /api/expenses/{id}/attachments（multipart：file + kind）；报销单 id 随每次上传传入（可能是刚自动保存的草稿） */
export function useUploadAttachment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ expenseId, file, kind }: { expenseId: string; file: File; kind: AttachmentKind }) => {
      const form = new FormData()
      form.append("file", file)
      form.append("kind", kind)
      return api.upload<AttachmentOut>(`/api/expenses/${expenseId}/attachments`, form)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: expenseKeys.all }),
    onError: notifyError,
  })
}

/** DELETE /api/attachments/{id}（仅草稿） */
export function useDeleteAttachment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (attachmentId: string) => api.delete<null>(`/api/attachments/${attachmentId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: expenseKeys.all }),
    onError: notifyError,
  })
}

/** DELETE /api/expenses/{id}（仅从未提交过的草稿，票据一并删除） */
export function useDeleteExpense() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete<null>(`/api/expenses/${id}`),
    // 已删掉的那张不再重新拉取（抽屉关闭前它的详情查询还挂着，重拉会 404）
    onSuccess: (_data, id) =>
      Promise.all([
        qc.removeQueries({ queryKey: expenseKeys.detail(id), exact: true }),
        qc.invalidateQueries({ queryKey: expenseKeys.all, predicate: (q) => !isExpenseDetailKey(q.queryKey, id) }),
        qc.invalidateQueries({ queryKey: dashboardKeys.all }),
      ]),
    onError: notifyError,
  })
}

/** POST /api/expenses/{id}/submit */
export function useSubmitExpense() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.post<ExpenseDetail>(`/api/expenses/${id}/submit`),
    onSuccess: () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: expenseKeys.all }),
        qc.invalidateQueries({ queryKey: dashboardKeys.all }),
        qc.invalidateQueries({ queryKey: ["approvals"] }),
      ]),
    onError: notifyError,
  })
}
