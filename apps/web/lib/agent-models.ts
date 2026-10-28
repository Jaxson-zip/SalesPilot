import { MODEL_OPTIONS } from "@/lib/agent-labels"
import type { ChatModels } from "@/types/api"

export interface ModelOption {
  value: string
  label: string
  available: boolean
  /** auto = 分组（按顺序失败切换）；model = 指定某个模型 */
  kind: "auto" | "model"
  /** 分组当前会先用哪个模型，例如「当前 DeepSeek」 */
  detail?: string
}

const LABELS = new Map(MODEL_OPTIONS.map((m) => [m.value, m.label]))
const labelOf = (id: string) => LABELS.get(id) ?? id

/**
 * 模型选择器的选项：以网关能力表为准（新接入的模型自动出现），没配 Key 的标记不可用。
 * 分组只保留对话默认分组（显示为「自动」），其他分组给别的场景用，不把内部 ID 露给销售。
 * 接口还没返回时先用内置选项，避免选择器闪烁。
 */
export function modelOptions(data: ChatModels | undefined): ModelOption[] {
  if (!data) {
    return MODEL_OPTIONS.map((m, i) => ({ ...m, available: true, kind: i === 0 ? "auto" : "model" }))
  }
  const groups = data.items.filter((m) => m.type === "group")
  const shown = groups.some((g) => g.id === data.default) ? groups.filter((g) => g.id === data.default) : groups
  const ready = new Set(data.items.filter((m) => m.type === "model" && m.available).map((m) => m.id))
  const autos: ModelOption[] = shown.map((g) => {
    const first = g.members.find((id) => ready.has(id))
    return {
      value: g.id,
      label: labelOf(g.id),
      available: g.available,
      kind: "auto",
      detail: first ? `当前 ${labelOf(first)}` : undefined,
    }
  })
  const models: ModelOption[] = data.items
    .filter((m) => m.type === "model")
    .map((m) => ({ value: m.id, label: labelOf(m.id), available: m.available, kind: "model" }))
  return [...autos, ...models]
}

/** 没有任何可用模型时的提示；有可用模型返回 null */
export function ruleModeHint(data: ChatModels | undefined): string | null {
  if (!data || data.any_available) return null
  return data.gateway_ok
    ? "未配置大模型 Key，当前为规则模式：能查客户、记跟进、出方案报价，回复为固定模板"
    : "模型网关未连接，当前为规则模式：能查客户、记跟进、出方案报价，回复为固定模板"
}
