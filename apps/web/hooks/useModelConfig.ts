"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"

export type ModelKind = "chat" | "embedding" | "rerank"
export type LinkType = "openai_compat" | "native"
/** 空 = 按模型清单（内置厂商已通过契约测试的协议） */
export type ProtocolChoice = "" | LinkType

export interface ModelCard {
  /** 网关里的模型别名，分组和对话选择器用它 */
  alias: string
  /** 上游模型名（原生协议带适配名前缀） */
  model: string
  link: string
  kind: ModelKind
  tools: boolean
  /** Embedding 的向量维度 */
  dims: number | null
  available: boolean
  unavailable_reason: string | null
  /** 厂商名（显示用） */
  provider: string
}

export interface BuiltinProvider {
  /** .env 里的变量名，如 DEEPSEEK_API_KEY */
  var: string
  label: string
  /** 在哪里申请 */
  hint: string
  /** web：网页上保存的；env：服务器 .env；none：都没有 */
  key_source: "web" | "env" | "none"
  /** Key 末 4 位（只有网页上保存、且足够长的才有） */
  tail: string | null
  saved_by: string | null
  saved_at: string | null
  /** 网页上存过，但加密密钥换过、解不开了 */
  broken: boolean
  /** 网页上改的接口地址；空 = 默认 */
  base: string
  default_base: string
  protocol: ProtocolChoice
  adapter: string
  /** 网关里这家的模型是否有可用的；网关连不上时为 null */
  available: boolean | null
  models: ModelCard[]
}

export interface ModelCapabilities {
  tools?: boolean
  stream?: boolean
  stream_tools?: boolean
  json_mode?: boolean
  dims?: number | null
}

export interface CustomModelInput {
  model: string
  kind: ModelKind
  capabilities: ModelCapabilities
}

export interface CustomModel extends CustomModelInput {
  alias: string
  available: boolean | null
  unavailable_reason: string | null
}

export interface CustomProvider {
  /** 厂商标识：模型别名的前缀，建好后不能改 */
  id: string
  name: string
  protocol: LinkType
  adapter: string
  api_base: string
  tail: string | null
  has_key: boolean
  broken: boolean
  saved_by: string | null
  saved_at: string | null
  available: boolean | null
  models: CustomModel[]
}

export interface Reindex {
  status: "idle" | "running" | "done" | "failed"
  target: string | null
  done: number
  total: number
  error: string | null
  by: string | null
  at: string | null
}

export interface ModelConfig {
  gateway_ok: boolean
  builtin: BuiltinProvider[]
  custom: CustomProvider[]
  /** chat-agent / embed / rerank → 模型别名（按顺序，第一个是主用） */
  groups: Record<string, string[]>
  /** models.yaml 里的默认 */
  group_defaults: Record<string, string[]>
  models: ModelCard[]
  /** 知识库要求的向量维度 */
  embedding_dims: number
  kb_chunks: number
  reindex: Reindex
  /** 接口地址允许指向内网 / 本机 */
  allow_private_base: boolean
}

export interface BuiltinInput {
  var: string
  /** 不传 = 不改；空字符串 = 清除网页上的 Key（回到 .env） */
  key?: string | null
  base: string
  protocol: ProtocolChoice
  adapter: string
}

export interface CustomInput {
  name: string
  protocol: LinkType
  adapter: string
  api_base: string
  /** 不传 = 不改 */
  key?: string | null
  models: CustomModelInput[]
}

export interface CustomTestInput {
  protocol: LinkType
  adapter: string
  api_base: string
  /** 不传 = 用这个厂商已保存的 */
  key?: string | null
  model: CustomModelInput
  detect: boolean
}

export interface GroupsInput {
  chat: string[]
  rerank: string[]
}

export interface ModelTestResult {
  ok: boolean
  model: string | null
  error: string | null
  dims: number | null
  capabilities: Record<string, boolean> | null
}

const KEY = ["integrations", "models"] as const
const URL = "/api/integrations/models"

/** GET /api/integrations/models（管理员）；重建知识库向量期间每 2 秒刷新进度 */
export function useModelConfig(enabled = true) {
  return useQuery({
    queryKey: KEY,
    enabled,
    queryFn: ({ signal }) => api.get<ModelConfig>(URL, undefined, signal),
    refetchInterval: (q) => (q.state.data?.reindex.status === "running" ? 2_000 : false),
  })
}

function useConfigMutation<B>(fn: (body: B) => Promise<ModelConfig>, done: (body: B) => string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (data, body) => {
      qc.setQueryData(KEY, data)
      if (!data.gateway_ok) toast.warning("已保存，模型网关暂时连不上，恢复后会自动生效")
      else toast.success(done(body))
    },
    onError: notifyError,
  })
}

export function useSaveBuiltin() {
  return useConfigMutation(
    (body: BuiltinInput) => api.put<ModelConfig>(`${URL}/builtin`, body),
    (body) => (body.key === "" ? "已清除网页上的 Key" : "已保存并生效"),
  )
}

export function useSaveCustom() {
  return useConfigMutation(
    ({ id, body }: { id: string; body: CustomInput }) =>
      api.put<ModelConfig>(`${URL}/custom/${encodeURIComponent(id)}`, body),
    () => "已保存并生效",
  )
}

export function useDeleteCustom() {
  return useConfigMutation(
    (id: string) => api.delete<ModelConfig>(`${URL}/custom/${encodeURIComponent(id)}`),
    () => "已删除",
  )
}

export function useSaveGroups() {
  return useConfigMutation(
    (body: GroupsInput) => api.put<ModelConfig>(`${URL}/groups`, body),
    () => "默认模型已保存并生效",
  )
}

export function useSwitchEmbedding() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (alias: string) => api.post<ModelConfig>(`${URL}/embedding`, { alias }),
    onSuccess: (data) => {
      qc.setQueryData(KEY, data)
      toast.success("开始重建知识库向量，完成后自动切换")
    },
    onError: notifyError,
  })
}

function report(r: ModelTestResult) {
  if (r.ok) toast.success("连接成功")
  else toast.error(r.error ? `连接失败：${r.error}` : "连接失败")
}

/** 测试内置厂商：用表单上的值，key 不填测当前生效的；不保存 */
export function useTestBuiltin() {
  return useMutation({
    mutationFn: (body: BuiltinInput) => api.post<ModelTestResult>(`${URL}/builtin/test`, body),
    onSuccess: report,
    onError: notifyError,
  })
}

/** 测试自定义模型：连得通就检测能力（对话）或向量维度（Embedding）；不保存 */
export function useTestCustom() {
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CustomTestInput }) =>
      api.post<ModelTestResult>(`${URL}/custom/${encodeURIComponent(id)}/test`, body),
    onSuccess: report,
    onError: notifyError,
  })
}
