"use client"

import { History, Loader2, Sparkles } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useEffect, useRef, useState } from "react"

import { ChatView } from "@/components/agent/ChatView"
import { Composer } from "@/components/agent/Composer"
import { HistorySheet } from "@/components/agent/HistorySheet"
import { Welcome } from "@/components/agent/Welcome"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { usePermissions } from "@/hooks/usePermissions"
import { DEFAULT_PACK_LABEL } from "@/lib/agent-labels"
import { aiThreadHref } from "@/lib/thread-history"

import { useAiWorkbench } from "./useAiWorkbench"

type Workbench = ReturnType<typeof useAiWorkbench>

/**
 * 当前会话与地址 `/ai?t=<id>` 同步（会话记录面板里的链接靠地址通信）：
 * - 地址变了（点会话记录某条 / 点「新对话」/ 刷新）→ 打开对应会话或清空
 * - 发出第一条消息生成了新会话 → 把 id 写进地址（replace，不多一条历史记录）
 */
function useThreadUrl(w: Workbench): () => void {
  const t = useSearchParams().get("t")
  const router = useRouter()
  const latest = useRef({ w, t })
  useEffect(() => {
    latest.current = { w, t }
  })

  useEffect(() => {
    const { w } = latest.current
    if (t) {
      if (t !== w.stream.threadId) void w.openThread(t)
    } else if (w.stream.threadId) {
      w.newChat()
    }
  }, [t])

  const threadId = w.stream.threadId
  useEffect(() => {
    if (threadId && threadId !== latest.current.t) router.replace(aiThreadHref(threadId), { scroll: false })
  }, [threadId, router])

  return () => router.push("/ai")
}

/** AI 方案工作台：居中会话 + 底部大输入框；会话记录在标题行「历史记录」打开的右侧面板里 */
function AiWorkbench() {
  const w = useAiWorkbench()
  const { stream, input, setInput, model, setModel, title, send } = w
  const { canAiWrite } = usePermissions()
  const goNew = useThreadUrl(w)
  const [historyOpen, setHistoryOpen] = useState(false)

  const composer = (welcome: boolean) => (
    <Composer
      value={input}
      onChange={setInput}
      onSubmit={() => send(input)}
      onStop={stream.stop}
      streaming={stream.isStreaming}
      model={model}
      onModelChange={setModel}
      pack={DEFAULT_PACK_LABEL}
      rows={welcome ? 3 : 2}
      placeholder={
        !canAiWrite
          ? "查询业务数据，例如：本月全公司销售漏斗怎么样"
          : welcome
            ? undefined
            : "继续追问，例如：换成 DeepSeek-V3 再算一版"
      }
    />
  )

  return (
    <PageFrame
      title="AI 方案工作台"
      icon={Sparkles}
      actions={<FrameAction icon={History} label="历史记录" onClick={() => setHistoryOpen(true)} />}
    >
      <HistorySheet open={historyOpen} onOpenChange={setHistoryOpen} activeId={stream.threadId} />
      <div className="relative flex min-h-0 flex-1">
        {stream.turns.length > 0 ? (
          <ChatView
            title={title}
            turns={stream.turns}
            busy={stream.isStreaming}
            loading={Boolean(w.loadingId)}
            composer={composer(false)}
            onDecide={stream.resume}
            onRetry={stream.retry}
            onNew={goNew}
          />
        ) : w.loadingId ? (
          <div className="flex flex-1 items-center justify-center gap-2 text-sm text-zinc-400">
            <Loader2 className="size-4 animate-spin" />
            正在加载会话…
          </div>
        ) : (
          <Welcome composer={composer(true)} onPick={send} readOnly={!canAiWrite} />
        )}
      </div>
    </PageFrame>
  )
}

export default function AiPage() {
  // useSearchParams 需要 Suspense 边界
  return (
    <Suspense fallback={null}>
      <AiWorkbench />
    </Suspense>
  )
}
