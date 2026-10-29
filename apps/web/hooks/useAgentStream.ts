"use client"

import { useCallback, useRef, useState } from "react"

import {
  applyAgentEvent,
  applyDecision,
  closeDanglingSteps,
  createAssistantTurn,
  finish,
  nextId,
  type AssistantTurn,
  type ChatTurn,
} from "@/lib/agent-reducer"
import { api, isAbortError, isApiError } from "@/lib/api"
import { MATERIAL_DEFAULT_ASK, type MaterialIn } from "@/lib/materials"
import { getSSE, postSSE, type StreamOptions } from "@/lib/sse"
import type { ThreadRunning } from "@/lib/thread-history"
import { ErrorCode, type ResumeDecision } from "@/types/api"

const CHAT_PATH = "/api/agent/chat"
const RESUME_PATH = "/api/agent/resume"
const threadPath = (id: string, tail: "stream" | "stop") => `/api/agent/threads/${encodeURIComponent(id)}/${tail}`

/** 切换会话 / 新对话时断开连接的原因：后台照常生成，本地不再更新这条回复 */
const DETACH = "detach"

function updateLastAssistant(turns: ChatTurn[], fn: (t: AssistantTurn) => AssistantTurn): ChatTurn[] {
  for (let i = turns.length - 1; i >= 0; i--) {
    const t = turns[i]
    if (t.role === "assistant") {
      const next = turns.slice()
      next[i] = fn(t)
      return next
    }
  }
  return turns
}

function toError(err: unknown): { code: number; message: string } {
  if (isApiError(err)) return { code: err.code, message: err.message }
  return { code: ErrorCode.NETWORK, message: "连接中断，请重试" }
}

export interface UseAgentStream {
  turns: ChatTurn[]
  threadId: string | null
  isStreaming: boolean
  /** opportunityId：从商机进入的会话，每条消息都带上，报价单关联到这个商机、行业包随商机产品线 */
  send: (message: string, model: string, material?: MaterialIn | null, opportunityId?: string | null) => void
  resume: (decision: ResumeDecision) => void
  stop: () => void
  retry: () => void
  reset: () => void
  /** 加载历史会话：替换当前消息并接上该 thread（之后的追问 / 确认都发到这个 thread） */
  load: (threadId: string, turns: ChatTurn[], lastMessage: string | null, model: string) => void
  /** 加载一个还在后台生成的会话：先显示本轮之前的内容，再订阅本轮（从头重放 + 实时） */
  attach: (threadId: string, turns: ChatTurn[], running: ThreadRunning, model: string) => void
}

type Patch = (fn: (t: AssistantTurn) => AssistantTurn) => void
type Open = (opts: StreamOptions) => Promise<void>

/**
 * 执行一次 SSE 订阅，把事件逐条应用到最后一条 AI 回复；负责停止 / 断开 / 错误收尾。
 * 生成在 core 后台进行，断开连接不会中断它（切页面、刷新后回来可以接着看）。
 */
function useStreamRunner(patch: Patch, onThread: (id: string) => void) {
  const [isStreaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const run = useCallback(
    async (open: Open) => {
      const ctrl = new AbortController()
      abortRef.current = ctrl
      setStreaming(true)
      const detached = () => ctrl.signal.reason === DETACH
      try {
        await open({
          signal: ctrl.signal,
          onEvent: (ev) => {
            if (detached()) return
            if (ev.event === "done" && ev.data.thread_id) onThread(ev.data.thread_id)
            patch((t) => applyAgentEvent(t, ev))
          },
        })
        // 流正常结束但没收到 done：按完成处理
        patch((t) => (t.status === "streaming" ? finish(t, "done") : t))
      } catch (err) {
        if (detached()) return
        if (isAbortError(err)) patch((t) => finish(closeDanglingSteps(t, "已停止"), "stopped"))
        else patch((t) => ({ ...finish(closeDanglingSteps(t, "连接中断"), "error"), error: toError(err) }))
      } finally {
        if (abortRef.current === ctrl) {
          abortRef.current = null
          setStreaming(false)
        }
      }
    },
    [patch, onThread],
  )

  /** 离开当前会话（不停止后台生成） */
  const detach = useCallback(() => {
    abortRef.current?.abort(DETACH)
    abortRef.current = null
    setStreaming(false)
  }, [])

  return { run, abortRef, isStreaming, detach }
}

/** 把 §8.3 的 SSE 事件流转成消息状态：步骤、正文增量、卡片、确认、完成、错误 */
export function useAgentStream(): UseAgentStream {
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [threadId, setThreadId] = useState<string | null>(null)
  const threadRef = useRef<string | null>(null)
  const lastChat = useRef<{
    message: string
    model: string
    material?: MaterialIn | null
    opportunity_id?: string
  } | null>(null)

  const patch = useCallback<Patch>((fn) => setTurns((ts) => updateLastAssistant(ts, fn)), [])
  const onThread = useCallback((id: string) => {
    threadRef.current = id
    setThreadId(id)
  }, [])
  const { run, abortRef, isStreaming, detach } = useStreamRunner(patch, onThread)

  const ensureThread = useCallback((): string => {
    if (!threadRef.current) {
      threadRef.current = nextId("t")
      setThreadId(threadRef.current)
    }
    return threadRef.current
  }, [])

  const send = useCallback(
    (message: string, model: string, material?: MaterialIn | null, opportunityId?: string | null) => {
      const text = message.trim() || (material ? MATERIAL_DEFAULT_ASK : "")
      if (!text || abortRef.current) return
      const opportunity_id = opportunityId ?? undefined
      lastChat.current = { message: text, model, material, opportunity_id }
      const thread_id = ensureThread()
      const meta = material ? { name: material.name, chars: material.text.length } : null
      setTurns((ts) => [...ts, { id: nextId("u"), role: "user", text, material: meta }, createAssistantTurn()])
      void run((o) =>
        postSSE(CHAT_PATH, { thread_id, message: text, model, material: material ?? undefined, opportunity_id }, o),
      )
    },
    [abortRef, ensureThread, run],
  )

  const resume = useCallback(
    (decision: ResumeDecision) => {
      const thread_id = threadRef.current
      if (!thread_id || abortRef.current) return
      patch((t) => applyDecision(t, decision))
      void run((o) => postSSE(RESUME_PATH, { thread_id, decision }, o))
    },
    [abortRef, patch, run],
  )

  const retry = useCallback(() => {
    const last = lastChat.current
    if (!last || abortRef.current) return
    const thread_id = ensureThread()
    setTurns((ts) => [...ts, createAssistantTurn()])
    void run((o) =>
      postSSE(
        CHAT_PATH,
        {
          thread_id,
          message: last.message,
          model: last.model,
          material: last.material ?? undefined,
          opportunity_id: last.opportunity_id,
        },
        o,
      ),
    )
  }, [abortRef, ensureThread, run])

  // 停止：先通知后台停下（断开连接不会让它停），再结束本地这条回复
  const stop = useCallback(() => {
    const id = threadRef.current
    if (id) void api.post(threadPath(id, "stop")).catch(() => undefined)
    abortRef.current?.abort()
  }, [abortRef])

  const reset = useCallback(() => {
    detach()
    threadRef.current = null
    lastChat.current = null
    setThreadId(null)
    setTurns([])
  }, [detach])

  const load = useCallback(
    (id: string, next: ChatTurn[], lastMessage: string | null, model: string) => {
      detach()
      threadRef.current = id
      lastChat.current = lastMessage ? { message: lastMessage, model } : null
      setThreadId(id)
      setTurns(next)
    },
    [detach],
  )

  const attach = useCallback(
    (id: string, base: ChatTurn[], running: ThreadRunning, model: string) => {
      detach()
      threadRef.current = id
      setThreadId(id)
      if (running.kind === "chat") {
        lastChat.current = { message: running.input, model }
        setTurns([...base, { id: nextId("u"), role: "user", text: running.input }, createAssistantTurn()])
      } else {
        const decision: ResumeDecision = running.input === "reject" ? "reject" : "approve"
        setTurns(updateLastAssistant(base, (t) => applyDecision(t, decision)))
      }
      void run((o) => getSSE(threadPath(id, "stream"), o))
    },
    [detach, run],
  )

  return { turns, threadId, isStreaming, send, resume, stop, retry, reset, load, attach }
}
