"use client"

import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo, useRef, useState } from "react"

import { notifyError } from "@/hooks/notify"
import { fetchThreadMessages, threadKeys, useAgentThreads } from "@/hooks/useAgentThreads"
import { useAgentStream } from "@/hooks/useAgentStream"
import { DEFAULT_MODEL } from "@/lib/agent-labels"
import { lastUserText, messagesToTurns, toHistoryItems } from "@/lib/thread-history"

/** AI 工作台页面状态：输入框、模型、会话历史（服务端会话列表 + 点击加载消息） */
export function useAiWorkbench() {
  const stream = useAgentStream()
  const qc = useQueryClient()
  const threads = useAgentThreads()
  const [input, setInput] = useState("")
  const [model, setModel] = useState(DEFAULT_MODEL)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const history = useMemo(() => toHistoryItems(threads.data?.items ?? []), [threads.data])

  // 一轮对话结束（流式 → 空闲）后刷新会话列表：新会话出现在历史里、旧会话排到最前。
  // 本轮确认执行过写操作（审批、改阶段、建任务…）时刷新全部业务数据，侧栏待审批数、通知等随之更新
  const wasStreaming = useRef(false)
  const last = stream.turns.at(-1)
  const wrote = last?.role === "assistant" && last.interrupt?.decision === "approve"
  useEffect(() => {
    if (wasStreaming.current && !stream.isStreaming) {
      void qc.invalidateQueries(wrote ? undefined : { queryKey: threadKeys.list })
    }
    wasStreaming.current = stream.isStreaming
  }, [stream.isStreaming, wrote, qc])

  const firstUser = stream.turns.find((t) => t.role === "user")
  const title = firstUser?.role === "user" ? firstUser.text : "新对话"

  const send = (text: string) => {
    const msg = text.trim()
    if (!msg || stream.isStreaming) return
    stream.send(msg, model)
    setInput("")
  }

  const newChat = () => {
    stream.reset()
    setInput("")
  }

  const openThread = async (id: string) => {
    if (id === stream.threadId || loadingId) return
    setLoadingId(id)
    try {
      const data = await qc.fetchQuery({
        queryKey: threadKeys.messages(id),
        queryFn: ({ signal }) => fetchThreadMessages(id, signal),
        staleTime: 0,
      })
      const turns = messagesToTurns(data)
      stream.load(id, turns, lastUserText(turns), model)
      setInput("")
    } catch (err) {
      notifyError(err)
    } finally {
      setLoadingId(null)
    }
  }

  return {
    stream,
    input,
    setInput,
    model,
    setModel,
    history,
    historyState: threads,
    loadingId,
    title,
    send,
    newChat,
    openThread,
  }
}
