/**
 * AI 会话历史：GET /api/agent/threads 与 GET /api/agent/threads/{id}/messages 的类型，
 * 以及「服务端消息 → 前端 ChatTurn」的纯函数转换（还原用户消息、AI 文字、卡片、待确认操作）。
 */
import { nextId, type AssistantTurn, type ChatTurn } from "@/lib/agent-reducer"
import { actionTitle } from "@/lib/agent-labels"

export interface ThreadSummary {
  thread_id: string
  title: string
  updated_at: string
  opportunity_id: string | null
}

export interface ThreadPage {
  items: ThreadSummary[]
  total: number
}

export interface ThreadMessage {
  role: "user" | "assistant"
  text: string
  artifacts?: { type: string; data: unknown }[]
  created_at?: string | null
}

export interface ThreadMessages {
  thread_id: string
  messages: ThreadMessage[]
  /** 会话停在写操作确认时的 interrupt 值（{action, preview}）；没有为 null */
  pending?: { action?: unknown; preview?: unknown } | null
}

/** 左侧会话历史的一项 */
export interface HistoryItem {
  id: string
  title: string
  /** 毫秒时间戳，用于「今天 / 7 天内」分组 */
  updatedAt: number
}

export function toHistoryItems(items: ThreadSummary[]): HistoryItem[] {
  return items.map((t) => {
    const ts = Date.parse(t.updated_at)
    return { id: t.thread_id, title: t.title || "新对话", updatedAt: Number.isNaN(ts) ? 0 : ts }
  })
}

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v)

function assistantTurn(m: ThreadMessage): AssistantTurn {
  const ts = m.created_at ? Date.parse(m.created_at) : NaN
  const at = Number.isNaN(ts) ? 0 : ts
  return {
    id: nextId("ai"),
    role: "assistant",
    steps: [],
    text: m.text,
    afterText: "",
    artifacts: (m.artifacts ?? []).map((a) => ({ id: nextId("art"), type: a.type, data: a.data })),
    interrupt: null,
    status: "done",
    error: null,
    currentNode: null,
    startedAt: at,
    endedAt: at,
  }
}

/** 服务端消息 → ChatTurn；有待确认操作时挂到最后一条 AI 回复上（可继续确认 / 取消） */
export function messagesToTurns(data: ThreadMessages): ChatTurn[] {
  const turns: ChatTurn[] = data.messages.map((m) =>
    m.role === "user" ? { id: nextId("u"), role: "user", text: m.text } : assistantTurn(m),
  )
  const p = data.pending
  const last = turns[turns.length - 1]
  if (p && typeof p.action === "string" && last?.role === "assistant") {
    const preview = isRecord(p.preview) ? p.preview : {}
    turns[turns.length - 1] = { ...last, interrupt: { action: p.action, title: actionTitle(p.action), preview } }
  }
  return turns
}

/** 最后一条用户消息（加载历史后「重新生成」用） */
export function lastUserText(turns: ChatTurn[]): string | null {
  for (let i = turns.length - 1; i >= 0; i--) {
    const t = turns[i]
    if (t.role === "user") return t.text
  }
  return null
}
