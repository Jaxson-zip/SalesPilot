"use client"

import { useState } from "react"

import type { HistoryItem } from "@/components/agent/ChatHistory"
import { useAgentStream } from "@/hooks/useAgentStream"
import { DEFAULT_MODEL } from "@/lib/agent-labels"

/** AI 工作台页面状态：输入框、模型、本地会话历史（会话列表接口就绪前只保存在内存） */
export function useAiWorkbench() {
  const stream = useAgentStream()
  const [input, setInput] = useState("")
  const [model, setModel] = useState(DEFAULT_MODEL)
  const [histOpen, setHistOpen] = useState(false)
  const [history, setHistory] = useState<HistoryItem[]>([])

  const firstUser = stream.turns.find((t) => t.role === "user")
  const title = firstUser?.role === "user" ? firstUser.text : "新对话"

  const send = (text: string) => {
    const msg = text.trim()
    if (!msg || stream.isStreaming) return
    stream.send(msg, model)
    setInput("")
    if (stream.turns.length === 0) {
      setHistory((h) => [{ id: `local_${Date.now()}`, title: msg, updatedAt: Date.now() }, ...h])
    }
  }

  const newChat = () => {
    stream.reset()
    setInput("")
    setHistOpen(false)
  }

  return { stream, input, setInput, model, setModel, histOpen, setHistOpen, history, title, send, newChat }
}
