import { actionTitle, toolTitle } from "@/lib/agent-labels"
import type { AgentEvent, ResumeDecision } from "@/types/api"

/** ThoughtChain 步骤的 5 种状态（§10.4） */
export type StepStatus = "done" | "running" | "retry" | "wait" | "error"

export interface AgentStep {
  id: string
  title: string
  tool: string
  status: StepStatus
  desc?: string
  args?: unknown
  result?: unknown
}

export interface AgentArtifact {
  id: string
  type: string
  data: unknown
}

export interface AgentInterrupt {
  action: string
  title: string
  preview: Record<string, unknown>
  decision?: ResumeDecision
}

export type TurnStatus = "streaming" | "done" | "error" | "stopped"

export interface UserTurn {
  id: string
  role: "user"
  text: string
}

export interface AssistantTurn {
  id: string
  role: "assistant"
  steps: AgentStep[]
  text: string
  /** 用户确认 / 取消之后的续写：显示在确认卡片下面，阅读顺序和发生顺序一致 */
  afterText: string
  artifacts: AgentArtifact[]
  interrupt: AgentInterrupt | null
  status: TurnStatus
  error: { code: number; message: string } | null
  currentNode: string | null
  startedAt: number
  endedAt: number | null
}

export type ChatTurn = UserTurn | AssistantTurn

let seq = 0
export const nextId = (prefix: string): string => `${prefix}_${Date.now().toString(36)}_${(seq++).toString(36)}`

export function createAssistantTurn(): AssistantTurn {
  return {
    id: nextId("ai"),
    role: "assistant",
    steps: [],
    text: "",
    afterText: "",
    artifacts: [],
    interrupt: null,
    status: "streaming",
    error: null,
    currentNode: null,
    startedAt: Date.now(),
    endedAt: null,
  }
}

function updateStep(turn: AssistantTurn, callId: string, patch: Partial<AgentStep>): AgentStep[] {
  return turn.steps.map((s) => (s.id === callId ? { ...s, ...patch } : s))
}

export const finish = (turn: AssistantTurn, status: TurnStatus): AssistantTurn => ({
  ...turn,
  status,
  currentNode: null,
  endedAt: Date.now(),
})

const addStep = (turn: AssistantTurn, step: AgentStep): AssistantTurn => ({ ...turn, steps: [...turn.steps, step] })

/** 步骤类事件：tool.start / tool.end / tool.error / node.retry */
function applyStepEvent(turn: AssistantTurn, ev: AgentEvent): AssistantTurn {
  switch (ev.event) {
    case "tool.start": {
      const { call_id, name, args } = ev.data
      return addStep(turn, { id: call_id, title: toolTitle(name), tool: name, status: "running", args })
    }
    case "tool.end": {
      const { call_id, summary, result } = ev.data
      return { ...turn, steps: updateStep(turn, call_id, { status: "done", desc: summary, result }) }
    }
    case "tool.error": {
      const desc = `错误码 ${ev.data.code}：${ev.data.message}`
      return { ...turn, steps: updateStep(turn, ev.data.call_id, { status: "error", desc }) }
    }
    case "node.retry": {
      const { node, reason, attempt } = ev.data
      const desc = `${reason}（第 ${attempt} 次尝试）`
      return addStep(turn, { id: nextId("retry"), title: toolTitle(node), tool: node, status: "retry", desc })
    }
    default:
      return turn
  }
}

const joinText = (a: string, b: string): string => (a && b ? `${a}\n\n${b}` : a || b)

/** 写操作中断：追加 wait 步骤并显示 ConfirmCard（同一条回复里第二次确认时，上一段续写并入正文） */
function applyInterrupt(turn: AssistantTurn, action: string, preview: Record<string, unknown>): AssistantTurn {
  const title = actionTitle(action)
  const merged = { ...turn, text: joinText(turn.text, turn.afterText), afterText: "" }
  const waiting = addStep(finish(merged, "done"), {
    id: nextId("wait"),
    title,
    tool: action,
    status: "wait",
    desc: "写操作，等待你确认",
  })
  return { ...waiting, interrupt: { action, title, preview } }
}

/**
 * 同一条回复里同类型的卡片只保留最新一份，并留在原来的位置。
 * 例如毛利回退后 core 会重新推送方案卡片，新结果应替换旧结果而不是重复显示。
 */
export function upsertArtifact(list: AgentArtifact[], type: string, data: unknown): AgentArtifact[] {
  const i = list.findIndex((a) => a.type === type)
  if (i === -1) return [...list, { id: nextId("art"), type, data }]
  return list.map((a, j) => (j === i ? { ...a, data } : a))
}

/** 纯函数：把一个 SSE 事件应用到当前 AI 回复上 */
export function applyAgentEvent(turn: AssistantTurn, ev: AgentEvent): AssistantTurn {
  switch (ev.event) {
    case "node.start":
      return { ...turn, currentNode: ev.data.node }
    case "interrupt":
      return applyInterrupt(turn, ev.data.action, ev.data.preview)
    case "artifact":
      return { ...turn, artifacts: upsertArtifact(turn.artifacts, ev.data.type, ev.data.data) }
    case "message.delta":
      return turn.interrupt?.decision
        ? { ...turn, afterText: turn.afterText + ev.data.text }
        : { ...turn, text: turn.text + ev.data.text }
    case "done":
      return finish(turn, "done")
    case "error":
      return { ...finish(turn, "error"), error: { code: ev.data.code, message: ev.data.message } }
    default:
      return applyStepEvent(turn, ev)
  }
}

/** 用户确认 / 取消后：标记决定，等待步骤改为 done，重新进入流式状态 */
export function applyDecision(turn: AssistantTurn, decision: ResumeDecision): AssistantTurn {
  if (!turn.interrupt) return turn
  return {
    ...turn,
    interrupt: { ...turn.interrupt, decision },
    steps: turn.steps.map((s) =>
      s.status === "wait" ? { ...s, status: "done", desc: decision === "approve" ? "已确认执行" : "已取消" } : s,
    ),
    status: "streaming",
    endedAt: null,
  }
}

/** 流结束时仍在 running 的步骤（被停止 / 断开）改为 error，便于重试 */
export function closeDanglingSteps(turn: AssistantTurn, reason: string): AssistantTurn {
  return {
    ...turn,
    steps: turn.steps.map((s) => (s.status === "running" ? { ...s, status: "error", desc: reason } : s)),
  }
}
