"use client"

import { usePathname, useRouter } from "next/navigation"
import { createContext, useContext, useEffect, useRef, type ReactNode } from "react"
import { toast } from "sonner"

import { useAiWorkbench } from "@/hooks/useAiWorkbench"
import { aiThreadHref } from "@/lib/thread-history"

export type AiSession = ReturnType<typeof useAiWorkbench>

const AiSessionContext = createContext<AiSession | null>(null)

/** 生成结束时用户不在 AI 工作台：提示一下，点「查看」回到这条会话 */
function useFinishedNotice(w: AiSession) {
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

/** AI 会话挂在应用外壳上：切换页面不丢失正在进行的对话 */
export function AiSessionProvider({ children }: { children: ReactNode }) {
  const w = useAiWorkbench()
  useFinishedNotice(w)
  return <AiSessionContext.Provider value={w}>{children}</AiSessionContext.Provider>
}

export function useAiSession(): AiSession {
  const ctx = useContext(AiSessionContext)
  if (!ctx) throw new Error("useAiSession 需要在 AiSessionProvider 里使用")
  return ctx
}

/** 侧栏等处只读当前是否在生成；不在 Provider 里时返回 false */
export function useAiStreaming(): boolean {
  return useContext(AiSessionContext)?.stream.isStreaming ?? false
}
