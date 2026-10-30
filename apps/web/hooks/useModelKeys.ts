"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"

export interface ProviderKey {
  /** .env 里的变量名，如 DEEPSEEK_API_KEY */
  var: string
  label: string
  /** 在哪里申请 */
  hint: string
  /** 网关里用这个 Key 的模型别名 */
  models: string[]
  /** web：网页上保存的；env：服务器 .env；none：都没有 */
  source: "web" | "env" | "none"
  /** Key 末 4 位（只有网页上保存的才有） */
  tail?: string | null
  saved_by?: string | null
  saved_at?: string | null
  /** 网页上存过，但服务器的 JWT_SECRET 换过、解不开了 */
  broken: boolean
  /** 用这个 Key 的模型是否有可用的；网关连不上时为 null */
  available?: boolean | null
}

export interface ModelKeys {
  gateway_ok: boolean
  providers: ProviderKey[]
}

export interface ModelKeyInput {
  var: string
  /** 空字符串 = 清除网页上保存的 Key（回到 .env） */
  key: string
}

export interface KeyTestResult {
  ok: boolean
  model?: string | null
  error?: string | null
}

const KEY = ["integrations", "model-keys"] as const
const URL = "/api/integrations/model-keys"

/** GET /api/integrations/model-keys（管理员） */
export function useModelKeys() {
  return useQuery({
    queryKey: KEY,
    queryFn: ({ signal }) => api.get<ModelKeys>(URL, undefined, signal),
  })
}

export function useSaveModelKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ModelKeyInput) => api.put<ModelKeys>(URL, body),
    onSuccess: (data, body) => {
      qc.setQueryData(KEY, data)
      if (!data.gateway_ok) toast.warning("已保存，模型网关暂时连不上，恢复后会自动生效")
      else toast.success(body.key ? "Key 已保存并生效" : "已清除网页上的 Key")
    },
    onError: notifyError,
  })
}

/** 测试连接：key 不填时测当前生效的 Key；不保存 */
export function useTestModelKey() {
  return useMutation({
    mutationFn: (body: { var: string; key?: string }) => api.post<KeyTestResult>(`${URL}/test`, body),
    onSuccess: (r) => {
      if (r.ok) toast.success("连接成功，Key 可用")
      else toast.error(r.error ? `连接失败：${r.error}` : "连接失败")
    },
    onError: notifyError,
  })
}
