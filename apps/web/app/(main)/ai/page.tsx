"use client"

import { PanelLeft, Sparkles } from "lucide-react"

import { ChatHistory } from "@/components/agent/ChatHistory"
import { ChatView } from "@/components/agent/ChatView"
import { Composer } from "@/components/agent/Composer"
import { Welcome } from "@/components/agent/Welcome"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { useDeleteThread, useRenameThread } from "@/hooks/useAgentThreads"
import { usePermissions } from "@/hooks/usePermissions"
import { DEFAULT_PACK_LABEL } from "@/lib/agent-labels"

import { useAiWorkbench } from "./useAiWorkbench"
import { useHistoryPanel } from "./useHistoryPanel"

/** AI 方案工作台（DeepSeek 布局：左历史 + 中间居中会话 + 底部大输入框） */
export default function AiPage() {
  const panel = useHistoryPanel()
  const w = useAiWorkbench(panel.closeOverlay)
  const { stream, input, setInput, model, setModel, history, title, send, newChat } = w
  const { canAiWrite } = usePermissions()
  const rename = useRenameThread()
  const remove = useDeleteThread()

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
      actions={
        <FrameAction icon={PanelLeft} label={panel.pinned ? "收起会话记录" : "展开会话记录"} onClick={panel.toggle} />
      }
    >
      <div className="relative flex min-h-0 flex-1">
        <ChatHistory
          items={history}
          status={w.historyState}
          activeId={stream.threadId}
          loadingId={w.loadingId}
          pinned={panel.pinned}
          overlay={panel.overlay}
          onClose={panel.toggle}
          onNew={newChat}
          onSelect={(id) => void w.openThread(id)}
          onRename={(id, title) => rename.mutate({ id, title })}
          onDelete={(id) =>
            remove.mutate(id, {
              // 删的是正在看的会话：回到新对话
              onSuccess: () => id === stream.threadId && newChat(),
            })
          }
        />
        {stream.turns.length === 0 ? (
          <Welcome composer={composer(true)} onPick={send} readOnly={!canAiWrite} />
        ) : (
          <ChatView
            title={title}
            turns={stream.turns}
            busy={stream.isStreaming}
            composer={composer(false)}
            onDecide={stream.resume}
            onRetry={stream.retry}
            onNew={newChat}
          />
        )}
      </div>
    </PageFrame>
  )
}
