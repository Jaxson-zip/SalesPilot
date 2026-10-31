"use client"

import { useQueryClient } from "@tanstack/react-query"
import { usePathname, useRouter } from "next/navigation"
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react"
import { toast } from "sonner"

import { useSession } from "@/components/shell/SessionProvider"
import { notifyError } from "@/hooks/notify"
import { fetchThreadMessages, threadKeys } from "@/hooks/useAgentThreads"
import { useAiWorkbench } from "@/hooks/useAiWorkbench"
import type { AgentMode } from "@/lib/agent-mode"
import { readStorage, writeStorage } from "@/lib/storage"
import { aiThreadHref } from "@/lib/thread-history"

type ModeSession = ReturnType<typeof useAiWorkbench>

export type AiSession = ModeSession & {
  /** 切换到另一种模式：显示那边上次的对话（没有就是空白），返回它的会话 id */
  switchMode: (mode: AgentMode) => string | null
  /** 打开一条会话：按会话本身的模式放到对应那边并切过去 */
  openThread: (id: string) => Promise<void>
  /** 刷新页面后回到这个模式上次的对话（会话已不存在时静默忽略） */
  restore: () => Promise<void>
  /** 切到某个模式并开一个新对话（从商机「出方案」带着上下文进来时用），返回那个模式的会话 */
  startIn: (mode: AgentMode) => ModeSession
  /** 两种模式各自是否在生成（切换按钮上显示后台进度） */
  streaming: Record<AgentMode, boolean>
}

const AiSessionContext = createContext<AiSession | null>(null)

const MODES: AgentMode[] = ["work", "learn"]
const lastKey = (userId: string, mode: AgentMode) => `sp.ai.${userId}.${mode}`
const modeKey = (userId: string) => `sp.ai.${userId}.mode`

/** 生成结束时用户不在 AI 工作台：提示一下，点「查看」回到这条会话 */
function useFinishedNotice(w: ModeSession) {
  const pathname = usePathname()
  const router = useRouter()
  const was = useRef(false)
  const last = w.stream.turns.at(-1)
  useEffect(() => {
    const streaming = w.stream.isStreaming
    if (was.current && !streaming && pathname !== "/ai" && w.stream.threadId && last?.role === "assistant") {
      const href = aiThreadHref(w.stream.threadId)
      const waiting = Boolean(last.interrupt && !last.interrupt.decision)
      if (last.status === "done" || waiting)
        toast.success(waiting ? "AI 方案已生成，等你确认" : "AI 回复已生成", {
          action: { label: "查看", onClick: () => router.push(href) },
        })
    }
    was.current = streaming
  }, [w.stream.isStreaming, w.stream.threadId, last, pathname, router])
}

/** 记住每个模式最近的会话：刷新页面后能回到原来的对话 */
function useRememberThread(userId: string | null, mode: AgentMode, threadId: string | null) {
  useEffect(() => {
    if (userId && threadId) writeStorage(lastKey(userId, mode), threadId)
  }, [userId, mode, threadId])
}

/**
 * AI 会话挂在应用外壳上：切换页面不丢失正在进行的对话。
 * 做方案、学习问答各有一条当前会话，互不影响；只有点「新对话」才清空当前这一边。
 */
export function AiSessionProvider({ children }: { children: ReactNode }) {
  const { userId } = useSession()
  const qc = useQueryClient()
  const work = useAiWorkbench("work")
  const learn = useAiWorkbench("learn")
  const sessions: Record<AgentMode, ModeSession> = { work, learn }
  const [active, setActive] = useState<AgentMode>("work")
  useFinishedNotice(work)
  useFinishedNotice(learn)
  useRememberThread(userId, "work", work.stream.threadId)
  useRememberThread(userId, "learn", learn.stream.threadId)

  const latest = useRef({ sessions, active, userId })
  useEffect(() => {
    latest.current = { sessions, active, userId }
  })

  // 账号信息比页面晚到（刷新时）：在那之前没选过模式，就回到这个人上次用的模式；
  // 换了账号：清掉上一个人的对话
  const seenUser = useRef<string | null>(null)
  const picked = useRef(false)
  if (userId && seenUser.current !== userId) {
    const switched = seenUser.current !== null
    seenUser.current = userId
    if (switched || !picked.current) {
      const mode = readStorage(modeKey(userId)) === "learn" ? "learn" : "work"
      if (mode !== active) setActive(mode)
      latest.current.active = mode
    }
    if (switched) queueMicrotask(() => MODES.forEach((m) => latest.current.sessions[m].newChat()))
  }

  const select = useCallback((mode: AgentMode) => {
    picked.current = true
    setActive(mode)
    latest.current.active = mode
    const id = latest.current.userId
    if (id) writeStorage(modeKey(id), mode)
  }, [])

  const switchMode = useCallback(
    (mode: AgentMode) => {
      select(mode)
      return latest.current.sessions[mode].stream.threadId
    },
    [select],
  )

  const open = useCallback(
    async (id: string, quiet: boolean) => {
      const { sessions, active } = latest.current
      const here = MODES.find((m) => sessions[m].stream.threadId === id)
      if (here) return select(here)
      try {
        const data = await sessions[active].loading(id, () =>
          qc.fetchQuery({
            queryKey: threadKeys.messages(id),
            queryFn: ({ signal }) => fetchThreadMessages(id, signal),
            staleTime: 0,
          }),
        )
        const mode = data.mode ?? "work"
        latest.current.sessions[mode].show(id, data)
        select(mode)
      } catch (err) {
        if (!quiet) notifyError(err)
        else if (latest.current.userId) writeStorage(lastKey(latest.current.userId, active), null)
      }
    },
    [qc, select],
  )

  // 账号信息还没到时先记下，到了再恢复
  const pendingRestore = useRef(false)
  const restore = useCallback(async () => {
    const { sessions, active, userId } = latest.current
    if (!userId) {
      pendingRestore.current = true
      return
    }
    if (sessions[active].stream.threadId) return
    const id = readStorage(lastKey(userId, active))
    if (id) await open(id, true)
  }, [open])
  useEffect(() => {
    if (!userId || !pendingRestore.current) return
    pendingRestore.current = false
    void restore()
  }, [userId, restore])

  // 点了「新对话」：这一边清空，也不再在刷新后恢复上一条
  const fresh = useCallback((mode: AgentMode) => {
    const { sessions, userId } = latest.current
    sessions[mode].newChat()
    if (userId) writeStorage(lastKey(userId, mode), null)
    return sessions[mode]
  }, [])

  const value: AiSession = {
    ...sessions[active],
    newChat: () => void fresh(active),
    startIn: (mode) => {
      select(mode)
      return fresh(mode)
    },
    switchMode,
    openThread: (id) => open(id, false),
    restore,
    streaming: { work: work.stream.isStreaming, learn: learn.stream.isStreaming },
  }
  return <AiSessionContext.Provider value={value}>{children}</AiSessionContext.Provider>
}

export function useAiSession(): AiSession {
  const ctx = useContext(AiSessionContext)
  if (!ctx) throw new Error("useAiSession 需要在 AiSessionProvider 里使用")
  return ctx
}

/** 侧栏等处只读当前是否在生成（任一模式）；不在 Provider 里时返回 false */
export function useAiStreaming(): boolean {
  const s = useContext(AiSessionContext)?.streaming
  return Boolean(s?.work || s?.learn)
}
