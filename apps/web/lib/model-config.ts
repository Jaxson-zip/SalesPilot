import type {
  BuiltinProvider,
  LinkType,
  ModelCard,
  ModelConfig,
  ModelKind,
  ProtocolChoice,
} from "@/hooks/useModelConfig"

export const KIND_LABELS: Record<ModelKind, string> = { chat: "对话", embedding: "向量", rerank: "重排" }

export const LINK_LABELS: Record<string, string> = {
  openai_compat: "OpenAI 兼容",
  native: "LiteLLM 原生",
}

/** 下拉框不能用空字符串当值：「按模型清单」用 default 表示，保存时换回空 */
export type ProtocolOption = "default" | LinkType

export const BUILTIN_PROTOCOLS: { value: ProtocolOption; label: string }[] = [
  { value: "default", label: "按模型清单（推荐）" },
  { value: "openai_compat", label: "OpenAI 兼容" },
  { value: "native", label: "LiteLLM 原生适配" },
]

export const CUSTOM_PROTOCOLS: { value: LinkType; label: string }[] = [
  { value: "openai_compat", label: "OpenAI 兼容（大多数厂商）" },
  { value: "native", label: "LiteLLM 原生适配" },
]

export const toOption = (p: ProtocolChoice): ProtocolOption => p || "default"
export const fromOption = (p: ProtocolOption): ProtocolChoice => (p === "default" ? "" : p)

export interface ProviderPreset {
  id: string
  name: string
  base: string
  hint?: string
}

/** 常见的 OpenAI 兼容厂商：选了自动填名称、标识和接口地址（以各家文档为准） */
export const CUSTOM_PRESETS: ProviderPreset[] = [
  { id: "kimi", name: "Kimi（月之暗面）", base: "https://api.moonshot.cn/v1" },
  { id: "zhipu", name: "智谱 GLM", base: "https://open.bigmodel.cn/api/paas/v4" },
  { id: "siliconflow", name: "硅基流动", base: "https://api.siliconflow.cn/v1" },
  { id: "ark", name: "火山方舟（豆包）", base: "https://ark.cn-beijing.volces.com/api/v3" },
  {
    id: "ollama",
    name: "本地 Ollama",
    base: "http://host.docker.internal:11434/v1",
    hint: "Ollama 不校验 Key，随便填一个即可（例如 ollama）；需要服务器 .env 设置 MODEL_ALLOW_PRIVATE_BASE=true",
  },
]

const ID_RE = /^[a-z][a-z0-9-]{1,23}$/

export function validId(id: string): boolean {
  return ID_RE.test(id)
}

/** 和后端 custom_alias 一致：厂商标识-模型名（小写，非字母数字点换成短横线） */
export function customAlias(providerId: string, model: string): string {
  const slug = model
    .toLowerCase()
    .replace(/[^a-z0-9.]+/g, "-")
    .replace(/^-+|-+$/g, "")
  return `${providerId}-${slug}`
}

/** 按名称猜一个厂商标识；名称不含字母时返回空，让管理员自己填 */
export function suggestId(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 24)
  return validId(slug) ? slug : ""
}

/** 某类默认模型的候选：对话要能调用工具；向量要和知识库维度一致（还没测出维度的也列出，切换时再校验） */
export function candidates(config: ModelConfig, kind: ModelKind): ModelCard[] {
  return config.models.filter((m) => {
    if (m.kind !== kind) return false
    if (kind === "chat") return m.tools
    if (kind === "embedding") return m.dims === null || m.dims === config.embedding_dims
    return true
  })
}

export function modelLabel(card: ModelCard | undefined, alias: string): string {
  return card ? `${card.provider} · ${card.alias}` : alias
}

export function moveItem<T>(list: T[], index: number, delta: -1 | 1): T[] {
  const to = index + delta
  if (to < 0 || to >= list.length) return list
  const next = [...list]
  ;[next[index], next[to]] = [next[to], next[index]]
  return next
}

export function sameList(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((v, i) => v === b[i])
}

/** Key 来自哪里，一句话 */
export function keySourceText(p: BuiltinProvider): string {
  if (p.key_source === "web") return p.tail ? `已填写 · 末 4 位 ${p.tail}` : "已填写"
  if (p.key_source === "env") return "用服务器配置的 Key"
  return "未填写"
}

/** 「通义千问（阿里云百炼）」→「通义千问」 */
export function shortName(label: string): string {
  return label.replace(/（.*?）|\(.*?\)/g, "").trim()
}

export interface StatusLine {
  label: string
  /** 正在用的模型（厂商名）；没有可用的为 null */
  value: string | null
  /** 排在后面的可用备用模型 */
  backups: string[]
}

/** 页面顶部的状态：对话、知识库、重排各自现在用谁 */
export function aiStatus(config: ModelConfig): StatusLine[] {
  const cards = new Map(config.models.map((m) => [m.alias, m]))
  const line = (label: string, group: string): StatusLine => {
    const ready = (config.groups[group] ?? []).map((a) => cards.get(a)).filter((m) => m?.available) as ModelCard[]
    const names = ready.map((m) => shortName(m.provider))
    return { label, value: names[0] ?? null, backups: [...new Set(names.slice(1))].filter((n) => n !== names[0]) }
  }
  return [line("对话", "chat-agent"), line("知识库", "embed"), line("重排", "rerank")]
}
