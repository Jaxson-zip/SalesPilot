"use client"

import { Share2, Sparkles } from "lucide-react"
import { toast } from "sonner"

import { ChatHistory } from "@/components/agent/ChatHistory"
import { ChatView } from "@/components/agent/ChatView"
import { Composer } from "@/components/agent/Composer"
import { Welcome } from "@/components/agent/Welcome"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { DEFAULT_PACK_LABEL } from "@/lib/agent-labels"

import { useAiWorkbench } from "./useAiWorkbench"

/** AI 方案工作台（DeepSeek 布局：左历史 + 中间居中会话 + 底部大输入框） */
export default function AiPage() {
  const { stream, input, setInput, model, setModel, histOpen, setHistOpen, history, title, send, newChat } =
    useAiWorkbench()

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
      placeholder={welcome ? undefined : "继续追问，例如：换成 DeepSeek-V3 再算一版"}
    />
  )

  return (
    <PageFrame title="AI 方案工作台" icon={Sparkles} actions={<FrameAction icon={Share2} label="分享" />}>
      <div className="relative flex min-h-0 flex-1">
        <ChatHistory
          items={history}
          activeId={stream.turns.length > 0 ? (history[0]?.id ?? null) : null}
          open={histOpen}
          onNew={newChat}
          onSelect={() => {
            setHistOpen(false)
            toast("历史会话加载接口开发中")
          }}
        />
        {stream.turns.length === 0 ? (
          <Welcome composer={composer(true)} onPick={send} />
        ) : (
          <ChatView
            title={title}
            turns={stream.turns}
            busy={stream.isStreaming}
            composer={composer(false)}
            onToggleHistory={() => setHistOpen((o) => !o)}
            onDecide={stream.resume}
            onRetry={stream.retry}
            onDelete={newChat}
          />
        )}
      </div>
    </PageFrame>
  )
}
