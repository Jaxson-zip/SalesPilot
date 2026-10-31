/**
 * AI 会话历史：GET /api/agent/threads 与 GET /api/agent/threads/{id}/messages 的类型，
 * 以及「服务端消息 → 前端 ChatTurn」的纯函数转换（还原用户消息、AI 文字、卡片、待确认操作）。
 */
import { nextId, type AssistantTurn, type ChatTurn } from "@/lib/agent-reducer"
import { actionTitle } from "@/lib/agent-labels"
import type { AgentMode } from "@/lib/agent-mode"

export interface ThreadSummary {
  thread_id: string
  title: string
  updated_at: string
  opportunity_id: string | null
  /** 会话模式：做方案 / 学习问答 */
  mode?: AgentMode
  /** 还在后台生成 */
  running?: boolean
}

export interface ThreadPage {
  items: ThreadSummary[]
  total: number
}

export interface ThreadMessage {
  role: "user" | "assistant"
  text: string
  material?: { name: string; chars: number } | null
  artifacts?: { type: string; data: unknown }[]
  created_at?: string | null
}

export interface ThreadMessages {
  thread_id: string
  messages: ThreadMessage[]
  /** 会话停在写操作确认时的 interrupt 值（{action, preview}）；没有为 null */
  pending?: { action?: unknown; preview?: unknown } | null
  /** 这一轮还在后台生成：messages 是本轮开始前的内容，接着订阅 /stream 重放本轮 */
  running?: ThreadRunning | null
  /** 会话关联的商机：重新打开后继续带上（行业包、需求清单都跟着它） */
  opportunity_id?: string | null
  /** 会话模式（新建时确定，之后沿用） */
  mode?: AgentMode
}

export interface ThreadRunning {
  kind: "chat" | "resume"
  /** chat：用户这一轮的消息；resume：approve / reject */
  input: string
}

/** 左侧会话历史的一项 */
export interface HistoryItem {
  id: string
  title: string
  /** 毫秒时间戳，用于「今天 / 7 天内」分组 */
  updatedAt: number
  running: boolean
  /** 学习问答模式的会话 */
  learn: boolean
}

export function toHistoryItems(items: ThreadSummary[]): HistoryItem[] {
  return items.map((t) => {
    const ts = Date.parse(t.updated_at)
    return {
      id: t.thread_id,
      title: t.title || "新对话",
      updatedAt: Number.isNaN(ts) ? 0 : ts,
      running: Boolean(t.running),
      learn: t.mode === "learn",
    }
  })
}

/** 会话记录里的时间：今天显示「14:32」，更早显示「10-26」（标题相同的会话靠它区分） */
export function historyTime(ts: number, now: Date = new Date()): string {
  if (!ts) return ""
  const d = new Date(ts)
  const pad = (n: number) => String(n).padStart(2, "0")
  const sameDay = d.toDateString() === now.toDateString()
  return sameDay ? `${pad(d.getHours())}:${pad(d.getMinutes())}` : `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
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
    m.role === "user" ? { id: nextId("u"), role: "user", text: m.text, material: m.material } : assistantTurn(m),
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

/** AI 工作台打开某个会话的地址（侧栏链接、刷新后恢复） */
export function aiThreadHref(id: string): string {
  return `/ai?t=${encodeURIComponent(id)}`
}

/**
 * 打开 AI 工作台并开一个新对话：预填 prompt（关联商机）。
 * send：直接发出去（商机「出方案」）；不传时只预填，销售补上需求后再发（客户页、粘贴纪要）。
 */
export function aiPrefillHref(prompt: string, opportunityId?: string, send = false): string {
  const opp = opportunityId ? `&opp=${encodeURIComponent(opportunityId)}` : ""
  return `/ai?prompt=${encodeURIComponent(prompt)}${opp}${send ? "&send=1" : ""}`
}

export interface OpportunityBrief {
  customer: string
  name: string
  /** 商机预计金额（分） */
  amount?: number | null
  /** 跟进记录（新的在前） */
  followups?: { content: string; occurred_at: string | null; created_at: string }[]
}

const MAX_NOTES = 6
const MAX_NOTE_CHARS = 300

/** 商机「出方案」直接发给 AI 的话：商机、预计金额、最近几条跟进记录（AI 从里面拆需求，缺什么会问） */
export function opportunityPrompt(o: OpportunityBrief): string {
  const lines = [`给「${o.customer}」的「${o.name}」商机出一份方案。`]
  if (o.amount) lines.push(`商机预计金额约 ¥${Math.round(o.amount / 100).toLocaleString("en-US")}。`)
  const notes = (o.followups ?? []).filter((f) => f.content.trim()).slice(0, MAX_NOTES)
  if (notes.length) {
    lines.push("最近的跟进记录：")
    for (const f of notes) {
      const day = (f.occurred_at ?? f.created_at).slice(5, 10)
      const text = f.content.trim().replace(/\s+/g, " ")
      lines.push(`- ${day} ${text.length > MAX_NOTE_CHARS ? `${text.slice(0, MAX_NOTE_CHARS)}…` : text}`)
    }
  } else {
    lines.push("还没有跟进记录，缺什么信息请直接问我。")
  }
  return lines.join("\n")
}

export function solutionPrompt(customer: string, opportunity?: string): string {
  return opportunity ? `给「${customer}」的「${opportunity}」商机出一份方案：` : `给「${customer}」出一份方案：`
}
