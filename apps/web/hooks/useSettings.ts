"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { productLineKeys } from "@/hooks/useProductLines"
import { api } from "@/lib/api"
import type { PackCatalogItem } from "@/lib/pack-rules"
import type { CatalogEdit, KnowledgeUploadOut, SettingsOut, SettingsUpdate } from "@/lib/settings"

export const settingsKeys = {
  all: ["settings"] as const,
  global: ["settings", "global"] as const,
  pack: (id: string) => ["settings", "pack", id] as const,
}

const enc = encodeURIComponent

/** 通用规则（null）或某个行业包的参数 */
const settingsPath = (packId: string | null) => (packId ? `/api/packs/${enc(packId)}/settings` : "/api/settings/rules")

/** GET /api/settings/rules 或 /api/packs/{id}/settings（仅管理员） */
export function useSettings(packId: string | null, enabled = true) {
  return useQuery({
    queryKey: packId ? settingsKeys.pack(packId) : settingsKeys.global,
    queryFn: ({ signal }) => api.get<SettingsOut>(settingsPath(packId), undefined, signal),
    enabled,
  })
}

/** PUT：保存一组改动（值为 null 表示恢复默认）；通用规则变了，行业包的默认值也跟着变，一起刷新 */
export function useUpdateSettings(packId: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: SettingsUpdate) => api.put<SettingsOut>(settingsPath(packId), body),
    onSuccess: (data, body) => {
      qc.setQueryData(packId ? settingsKeys.pack(packId) : settingsKeys.global, data)
      void qc.invalidateQueries({ queryKey: settingsKeys.all })
      void qc.invalidateQueries({ queryKey: productLineKeys.packs })
      const reset = Object.values(body.values).every((v) => v === null)
      toast.success(reset ? "已恢复默认值，立即生效" : "已保存，立即生效")
    },
    onError: notifyError,
  })
}

/** PUT /api/packs/{id}/catalog/{sku}：改名称 / 单位 / 成本 / 售价；reset 时 DELETE 恢复默认 */
export function useUpdateCatalogItem(packId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ sku, edit }: { sku: string; edit: CatalogEdit | null }) => {
      const path = `/api/packs/${enc(packId)}/catalog/${enc(sku)}`
      return edit ? api.put<PackCatalogItem[]>(path, edit) : api.delete<PackCatalogItem[]>(path)
    },
    onSuccess: (_d, { edit }) => {
      toast.success(edit ? "价格已更新，新报价立即使用" : "已恢复目录默认价")
      void qc.invalidateQueries({ queryKey: productLineKeys.packs })
    },
    onError: notifyError,
  })
}

/** POST /api/packs/{id}/knowledge：上传并立即入库 */
export function useUploadKnowledge(packId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append("file", file)
      return api.upload<KnowledgeUploadOut>(`/api/packs/${enc(packId)}/knowledge`, form)
    },
    onSuccess: (d) => {
      toast.success(`「${d.doc_name}」已入库（${d.chunks} 段），AI 现在就能检索到`)
      void qc.invalidateQueries({ queryKey: productLineKeys.packs })
    },
    onError: notifyError,
  })
}

/** DELETE /api/packs/{id}/knowledge/{doc}：只能删网页上传的文档 */
export function useDeleteKnowledge(packId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (docName: string) => api.delete(`/api/packs/${enc(packId)}/knowledge/${enc(docName)}`),
    onSuccess: () => {
      toast.success("文档已删除，不再参与检索")
      void qc.invalidateQueries({ queryKey: productLineKeys.packs })
    },
    onError: notifyError,
  })
}
