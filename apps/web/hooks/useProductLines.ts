"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"
import type { PackDetail } from "@/lib/pack-rules"
import type { PackOut, Paged, ProductLineItem, ProductLineUpdate } from "@/types/api"

export const productLineKeys = {
  all: ["product-lines"] as const,
  packs: ["packs"] as const,
}

/** 列表可能返回 {items,total} 或直接数组，两种都兼容 */
function toList<T>(data: Paged<T> | T[]): T[] {
  return Array.isArray(data) ? data : data.items
}

/** GET /api/product-lines（所有角色可读；非管理员只返回已启用的产品线） */
export function useProductLines(enabled = true) {
  return useQuery({
    queryKey: productLineKeys.all,
    queryFn: async ({ signal }) =>
      toList(await api.get<Paged<ProductLineItem> | ProductLineItem[]>("/api/product-lines", undefined, signal)),
    enabled,
  })
}

/** GET /api/packs（已安装行业包） */
export function usePacks() {
  return useQuery({
    queryKey: productLineKeys.packs,
    queryFn: ({ signal }) => api.get<PackOut[]>("/api/packs", undefined, signal),
    staleTime: 5 * 60_000,
  })
}

/**
 * 行业包 id → 名称（如 llm_deploy → 大模型部署）。名称来自 core 的 /api/packs，前端不写死；
 * 还没加载到时先显示 id。
 */
export function usePackName(): (id: string | null | undefined) => string {
  const { data } = usePacks()
  return (id) => (id ? (data?.find((p) => p.id === id)?.name ?? id) : "—")
}

export interface DefaultPack {
  pack: string
  /** 团队默认产品线；没设时为 null（用系统默认行业包） */
  product_line: string | null
}

/** GET /api/agent/pack：不从商机进入时 AI 用哪个行业包（团队默认产品线，没设就用系统默认） */
export function useDefaultPack() {
  return useQuery({
    queryKey: [...productLineKeys.packs, "default"],
    queryFn: ({ signal }) => api.get<DefaultPack>("/api/agent/pack", undefined, signal),
  })
}

/** PUT /api/product-lines/{id}（pack 必须是已安装行业包，否则 40001） */
export function useUpdateProductLine() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: ProductLineUpdate & { id: string }) =>
      api.put<ProductLineItem>(`/api/product-lines/${id}`, body),
    onMutate: async ({ id, ...body }) => {
      await qc.cancelQueries({ queryKey: productLineKeys.all })
      const prev = qc.getQueryData<ProductLineItem[]>(productLineKeys.all)
      qc.setQueryData<ProductLineItem[]>(productLineKeys.all, (old) =>
        old?.map((pl) => (pl.id === id ? { ...pl, ...body } : pl)),
      )
      return { prev }
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(productLineKeys.all, ctx.prev)
      notifyError(err)
    },
    onSuccess: () => toast.success("产品线映射已保存"),
    onSettled: () => qc.invalidateQueries({ queryKey: productLineKeys.all }),
  })
}

/** GET /api/packs/{pack_id}：产品目录、业务规则、知识库文档（只读） */
export function usePackDetail(id: string | null) {
  return useQuery({
    queryKey: [...productLineKeys.packs, id ?? ""],
    queryFn: ({ signal }) => api.get<PackDetail>(`/api/packs/${encodeURIComponent(id ?? "")}`, undefined, signal),
    enabled: Boolean(id),
    staleTime: 5 * 60_000,
  })
}
