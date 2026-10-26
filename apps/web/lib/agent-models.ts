import { MODEL_OPTIONS } from "@/lib/agent-labels"
import type { ChatModels } from "@/types/api"

export interface ModelOption {
  value: string
  label: string
  available: boolean
}

const LABELS = new Map(MODEL_OPTIONS.map((m) => [m.value, m.label]))

/**
 * 模型选择器的选项：以网关能力表为准（新接入的模型自动出现），没配 Key 的标记不可用。
 * 接口还没返回时先用内置选项，避免选择器闪烁。
 */
export function modelOptions(data: ChatModels | undefined): ModelOption[] {
  if (!data) return MODEL_OPTIONS.map((m) => ({ ...m, available: true }))
  const groups = data.items.filter((m) => m.type === "group")
  const models = data.items.filter((m) => m.type === "model")
  return [...groups, ...models].map((m) => ({
    value: m.id,
    label: LABELS.get(m.id) ?? m.id,
    available: m.available,
  }))
}

/** 没有任何可用模型时的提示；有可用模型返回 null */
export function ruleModeHint(data: ChatModels | undefined): string | null {
  if (!data || data.any_available) return null
  return data.gateway_ok
    ? "未配置大模型 Key，当前为规则模式：能查客户、记跟进、出方案报价，回复为固定模板"
    : "模型网关未连接，当前为规则模式：能查客户、记跟进、出方案报价，回复为固定模板"
}
