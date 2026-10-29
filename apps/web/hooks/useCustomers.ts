"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { useDebounced } from "@/hooks/useDebounced"
import { activityKeys } from "@/hooks/useDashboard"
import { api } from "@/lib/api"
import type { ImportResult } from "@/lib/customer-import"
import { serverQuery, type ServerListParams } from "@/lib/list-view"
import type {
  Customer,
  CustomerCreate,
  CustomerDetail,
  CustomerListParams,
  CustomerTransferIn,
  HandoverIn,
  HandoverResult,
  CustomerUpdate,
  PoolRelease,
  Paged,
  SimilarCustomer,
} from "@/types/api"

export const customerKeys = {
  all: ["customers"] as const,
  list: (p: CustomerListParams & { q?: string }, l?: ServerListParams) => ["customers", "list", p, l] as const,
  detail: (id: string) => ["customers", "detail", id] as const,
  similar: (name: string) => ["customers", "similar", name] as const,
  pool: ["customers", "pool"] as const,
  poolPage: (page: number, l?: ServerListParams) => ["customers", "pool", page, l] as const,
}

/** GET /api/customers?view=&q=&page=&page_size=（list：服务端筛选 / 排序） */
export function useCustomers(params: CustomerListParams & { q?: string }, enabled = true, list?: ServerListParams) {
  return useQuery({
    queryKey: customerKeys.list(params, list),
    queryFn: ({ signal }) =>
      api.get<Paged<Customer>>(
        "/api/customers",
        {
          view: params.view,
          q: params.q || undefined,
          page: params.page,
          page_size: params.page_size,
          ...serverQuery(list ?? {}),
        },
        signal,
      ),
    placeholderData: keepPreviousData,
    enabled,
  })
}

/** GET /api/customers/pool：本团队公海（B5），服务端分页 */
export function usePoolCustomers(enabled = true, page = 1, pageSize = 100, list?: ServerListParams) {
  return useQuery({
    queryKey: customerKeys.poolPage(page, list),
    queryFn: ({ signal }) =>
      api.get<Paged<Customer>>(
        "/api/customers/pool",
        { page, page_size: pageSize, ...serverQuery(list ?? {}) },
        signal,
      ),
    placeholderData: keepPreviousData,
    enabled,
  })
}

/** GET /api/customers/{id} */
export function useCustomer(id: string) {
  return useQuery({
    queryKey: customerKeys.detail(id),
    queryFn: ({ signal }) => api.get<CustomerDetail>(`/api/customers/${id}`, undefined, signal),
    enabled: Boolean(id),
  })
}

/** GET /api/customers/similar：输入客户名称时查重（停顿 400ms 后再查，至少 2 个字） */
export function useSimilarCustomers(name: string) {
  const q = useDebounced(name.trim())
  return useQuery({
    queryKey: customerKeys.similar(q),
    queryFn: ({ signal }) => api.get<SimilarCustomer[]>("/api/customers/similar", { name: q }, signal),
    enabled: q.length >= 2,
    staleTime: 30_000,
  })
}

/** POST /api/customers：成功后刷新客户列表并写入详情缓存 */
export function useCreateCustomer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CustomerCreate) => api.post<CustomerDetail>("/api/customers", body),
    onSuccess: (c) => {
      qc.setQueryData(customerKeys.detail(c.id), c)
      toast.success("客户已创建", { description: c.name })
      void qc.invalidateQueries({ queryKey: customerKeys.all })
      void qc.invalidateQueries({ queryKey: activityKeys.all })
    },
    onError: notifyError,
  })
}

/** PATCH /api/customers/{id}（U10 行内编辑，仅负责人） */
export function useUpdateCustomer(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CustomerUpdate) => api.patch<CustomerDetail>(`/api/customers/${id}`, body),
    onSuccess: (c) => {
      qc.setQueryData(customerKeys.detail(id), c)
      toast.success("已保存")
      void qc.invalidateQueries({ queryKey: customerKeys.all })
      void qc.invalidateQueries({ queryKey: activityKeys.all })
    },
    onError: notifyError,
  })
}

function usePoolMutation<V>(id: string, path: "release" | "claim", done: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: V) => api.post<CustomerDetail>(`/api/customers/${id}/${path}`, body ?? {}),
    onSuccess: (c) => {
      qc.setQueryData(customerKeys.detail(id), c)
      toast.success(done, { description: c.name })
      void qc.invalidateQueries({ queryKey: customerKeys.all })
      void qc.invalidateQueries({ queryKey: activityKeys.all })
    },
    onError: notifyError,
  })
}

/** POST /api/customers/{id}/release：退回公海（负责人或本团队主管；有进行中商机时 42201） */
export const useReleaseCustomer = (id: string) => usePoolMutation<PoolRelease>(id, "release", "已退回公海")

/** POST /api/customers/{id}/claim：从公海领取（仅销售，先到先得） */
export const useClaimCustomer = (id: string) => usePoolMutation<void>(id, "claim", "已领取客户")

/** POST /api/customers/transfer（v3 §16，仅主管）：客户及其未结束的商机、未完成的任务、未成交的报价一起转移 */
export function useTransferCustomers() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CustomerTransferIn) => api.post<{ transferred: number }>("/api/customers/transfer", body),
    onSuccess: () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: customerKeys.all }),
        qc.invalidateQueries({ queryKey: ["opportunities"] }),
        qc.invalidateQueries({ queryKey: ["quotes"] }),
        qc.invalidateQueries({ queryKey: ["tasks"] }),
        qc.invalidateQueries({ queryKey: activityKeys.all }),
      ]),
    onError: notifyError,
  })
}

/** GET /api/customers/handover/preview：交接前看这个人名下有多少客户和进行中的业务 */
export function useHandoverPreview(fromUserId: string) {
  return useQuery({
    queryKey: ["customers", "handover", fromUserId] as const,
    queryFn: ({ signal }) =>
      api.get<HandoverResult>("/api/customers/handover/preview", { from_user_id: fromUserId }, signal),
    enabled: Boolean(fromUserId),
  })
}

/** POST /api/customers/handover（仅主管）：把一个人名下全部客户、进行中的业务和回款中的合同转给接手人 */
export function useHandover() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: HandoverIn) => api.post<HandoverResult>("/api/customers/handover", body),
    onSuccess: () =>
      Promise.all(
        [customerKeys.all, ["opportunities"], ["quotes"], ["tasks"], ["contracts"], activityKeys.all].map((queryKey) =>
          qc.invalidateQueries({ queryKey }),
        ),
      ),
    onError: notifyError,
  })
}

function importForm(file: File): FormData {
  const form = new FormData()
  form.append("file", file)
  return form
}

/** POST /api/customers/import/preview：逐行校验、查重，不写入 */
export function usePreviewImport() {
  return useMutation({
    mutationFn: (file: File) => api.upload<ImportResult>("/api/customers/import/preview", importForm(file)),
    onError: notifyError,
  })
}

/** POST /api/customers/import：有问题的行跳过，其余一次写入 */
export function useImportCustomers() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => api.upload<ImportResult>("/api/customers/import", importForm(file)),
    onSuccess: (r) => {
      toast.success(`已导入 ${r.ok} 个客户`, { description: r.skipped ? `跳过 ${r.skipped} 行` : undefined })
      void qc.invalidateQueries({ queryKey: customerKeys.all })
      void qc.invalidateQueries({ queryKey: activityKeys.all })
    },
    onError: notifyError,
  })
}
