"use client"

import { Sparkles } from "lucide-react"

import { ChatHistory } from "@/components/agent/ChatHistory"
import { ChatView } from "@/components/agent/ChatView"
import { Composer } from "@/components/agent/Composer"
import { Welcome } from "@/components/agent/Welcome"
import { PageFrame } from "@/components/biz/PageFrame"
import { usePermissions } from "@/hooks/usePermissions"
import { DEFAULT_PACK_LABEL } from "@/lib/agent-labels"

import { useAiWorkbench } from "./useAiWorkbench"

/** AI 方案工作台（DeepSeek 布局：左历史 + 中间居中会话 + 底部大输入框） */
export default function AiPage() {
  const w = useAiWorkbench()
  const { stream, input, setInput, model, setModel, histOpen, setHistOpen, history, title, send, newChat } = w
  const { canAiWrite } = usePermissions()

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
    <PageFrame title="AI 方案工作台" icon={Sparkles}>
      <div className="relative flex min-h-0 flex-1">
        <ChatHistory
          items={history}
          status={w.historyState}
          activeId={stream.threadId}
          loadingId={w.loadingId}
          open={histOpen}
          onNew={newChat}
          onSelect={(id) => void w.openThread(id)}
        />
        {stream.turns.length === 0 ? (
          <Welcome composer={composer(true)} onPick={send} readOnly={!canAiWrite} />
        ) : (
          <ChatView
            title={title}
            turns={stream.turns}
            busy={stream.isStreaming}
            composer={composer(false)}
            onToggleHistory={() => setHistOpen((o) => !o)}
            onDecide={stream.resume}
            onRetry={stream.retry}
            onNew={newChat}
          />
        )}
      </div>
    </PageFrame>
  )
}
