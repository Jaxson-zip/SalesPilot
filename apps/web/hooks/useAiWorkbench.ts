"use client"

import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"

import { notifyError } from "@/hooks/notify"
import { fetchThreadMessages, threadKeys } from "@/hooks/useAgentThreads"
import { useAgentStream } from "@/hooks/useAgentStream"
import { requirementKey } from "@/hooks/useRequirement"
import { DEFAULT_MODEL } from "@/lib/agent-labels"
import { extractMaterial, type MaterialOut } from "@/lib/materials"
import { lastUserText, messagesToTurns } from "@/lib/thread-history"

/**
 * AI 工作台状态：输入框、模型、当前会话、会话历史。
 * 由 AiSessionProvider 挂在整个应用外壳上（不随页面卸载）：生成到一半切去别的页面，回来还在，并且接着输出。
 */
export function useAiWorkbench() {
  const stream = useAgentStream()
  const qc = useQueryClient()
  const [input, setInput] = useState("")
  const [model, setModel] = useState(DEFAULT_MODEL)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [material, setMaterial] = useState<MaterialOut | null>(null)
  const [uploading, setUploading] = useState(false)
  // 从商机「出方案」进入时关联的商机；新对话 / 打开历史会话时清空
  const [opportunityId, setOpportunityId] = useState<string | null>(null)

  /** 上传材料：服务端解析成文字（不入库），发送时随消息一起交给 AI */
  const attach = async (file: File) => {
    setUploading(true)
    try {
      setMaterial(await extractMaterial(file))
    } catch (err) {
      notifyError(err)
    } finally {
      setUploading(false)
    }
  }

  // 一轮对话结束（流式 → 空闲）后刷新会话列表：新会话出现在历史里、旧会话排到最前。
  // 本轮确认执行过写操作（审批、改阶段、建任务…）时刷新全部业务数据，侧栏待审批数、通知等随之更新
  const wasStreaming = useRef(false)
  const last = stream.turns.at(-1)
  const wrote = last?.role === "assistant" && last.interrupt?.decision === "approve"
  useEffect(() => {
    if (wasStreaming.current && !stream.isStreaming) {
      void qc.invalidateQueries(wrote ? undefined : { queryKey: threadKeys.list })
      // 出方案会把需求清单存到商机上
      if (opportunityId) void qc.invalidateQueries({ queryKey: requirementKey(opportunityId) })
    }
    wasStreaming.current = stream.isStreaming
  }, [stream.isStreaming, wrote, qc, opportunityId])

  const firstUser = stream.turns.find((t) => t.role === "user")
  const title = firstUser?.role === "user" ? firstUser.text : "新对话"

  const send = (text: string) => {
    const msg = text.trim()
    if ((!msg && !material) || stream.isStreaming) return
    stream.send(msg, model, material ? { name: material.name, text: material.text } : null, opportunityId)
    setInput("")
    setMaterial(null)
  }

  /** 需求卡片「确认需求，出报价」：把核对后的需求随消息提交 */
  const confirmRequirement = (requirement: Record<string, unknown>) => {
    if (stream.isStreaming) return
    stream.send("需求已确认，出正式报价", model, null, opportunityId, requirement)
  }

  const newChat = () => {
    stream.reset()
    setInput("")
    setMaterial(null)
    setOpportunityId(null)
  }

  const openThread = async (id: string) => {
    if (id === stream.threadId || loadingId) return
    setLoadingId(id)
    setOpportunityId(null)
    try {
      const data = await qc.fetchQuery({
        queryKey: threadKeys.messages(id),
        queryFn: ({ signal }) => fetchThreadMessages(id, signal),
        staleTime: 0,
      })
      const turns = messagesToTurns(data)
      setOpportunityId(data.opportunity_id ?? null)
      // 这一轮还在后台生成（例如刷新了页面）：先显示之前的内容，再接上本轮
      if (data.running) stream.attach(id, turns, data.running, model)
      else stream.load(id, turns, lastUserText(turns), model)
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
    loadingId,
    material,
    uploading,
    attach,
    clearMaterial: () => setMaterial(null),
    title,
    send,
    confirmRequirement,
    newChat,
    openThread,
    opportunityId,
    setOpportunityId,
  }
}
