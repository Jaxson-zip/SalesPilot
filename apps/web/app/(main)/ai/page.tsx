"use client"

import { History, Loader2, Sparkles } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useEffect, useRef, useState } from "react"

import { useAiSession, type AiSession } from "@/components/agent/AiSessionProvider"
import { ChatView } from "@/components/agent/ChatView"
import { Composer } from "@/components/agent/Composer"
import { HistorySheet } from "@/components/agent/HistorySheet"
import { Welcome } from "@/components/agent/Welcome"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { useOpportunity } from "@/hooks/useOpportunities"
import { usePermissions } from "@/hooks/usePermissions"
import { usePackName } from "@/hooks/useProductLines"
import { DEFAULT_PACK_LABEL } from "@/lib/agent-labels"
import { takePastedMaterial } from "@/lib/materials"
import { aiThreadHref } from "@/lib/thread-history"

/**
 * 当前会话与地址 `/ai?t=<id>` 同步（会话记录面板里的链接靠地址通信）：
 * - 地址变了（点会话记录某条 / 点「新对话」/ 刷新）→ 打开对应会话或清空
 * - 从别的页面回到 `/ai`（地址没有 t）而会话还在 → 保留会话，把 id 补回地址
 * - 发出第一条消息生成了新会话 → 把 id 写进地址（replace，不多一条历史记录）
 */
function useThreadUrl(w: AiSession): () => void {
  const params = useSearchParams()
  const t = params.get("t")
  const prompt = params.get("prompt")
  const opp = params.get("opp")
  const paste = params.get("paste") === "1"
  const mode = params.get("mode")
  const router = useRouter()
  const latest = useRef({ w, t })
  const mounted = useRef(false)
  useEffect(() => {
    latest.current = { w, t }
  })

  useEffect(() => {
    const { w } = latest.current
    const first = !mounted.current
    mounted.current = true
    if (t) {
      if (t !== w.stream.threadId) void w.openThread(t)
    } else if (w.stream.threadId && !first) {
      w.newChat()
    }
  }, [t])

  // ?prompt=：从客户 / 商机页带过来的上下文，开新对话并预填输入框（不自动发送），然后去掉参数
  useEffect(() => {
    if (prompt === null) return
    latest.current.w.newChat()
    latest.current.w.switchMode("work")
    latest.current.w.setInput(prompt)
    latest.current.w.setOpportunityId(opp)
    // &paste=1：写跟进处粘贴的纪要，作为材料带进来（不自动发送，销售看一眼再发）
    const pasted = paste ? takePastedMaterial() : null
    if (pasted) latest.current.w.loadMaterial(pasted)
    router.replace("/ai", { scroll: false })
  }, [prompt, opp, paste, router])

  // ?mode=learn：直接打开学习问答（新对话）
  useEffect(() => {
    if (mode !== "learn") return
    latest.current.w.switchMode("learn")
    router.replace("/ai", { scroll: false })
  }, [mode, router])

  const threadId = w.stream.threadId
  useEffect(() => {
    if (threadId && threadId !== latest.current.t) router.replace(aiThreadHref(threadId), { scroll: false })
  }, [threadId, router])

  return () => router.push("/ai")
}

/** AI 方案工作台：居中会话 + 底部大输入框；会话记录在标题行「历史记录」打开的右侧面板里 */
function AiWorkbench() {
  const w = useAiSession()
  const { stream, input, setInput, model, setModel, title, send } = w
  const { canAiWrite } = usePermissions()
  const goNew = useThreadUrl(w)
  // 从商机进入：显示该商机产品线对应的行业包；否则显示团队默认行业包
  const opp = useOpportunity(w.opportunityId)
  const packName = usePackName()
  const pack = opp.data?.product_line ? packName(opp.data.product_line.pack) : DEFAULT_PACK_LABEL
  const [historyOpen, setHistoryOpen] = useState(false)
  const learn = w.mode === "learn"
  const canAttach = canAiWrite && !learn

  const composer = (welcome: boolean) => (
    <Composer
      value={input}
      onChange={setInput}
      onSubmit={() => send(input)}
      onStop={stream.stop}
      material={canAttach ? w.material : undefined}
      uploading={w.uploading}
      onAttach={canAttach ? (f) => void w.attach(f) : undefined}
      onClearMaterial={w.clearMaterial}
      samples={canAttach ? w.samples : undefined}
      onAttachSamples={canAttach ? w.attachSamples : undefined}
      onRetrySamples={w.retrySamples}
      onClearSamples={w.clearSamples}
      streaming={stream.isStreaming}
      model={model}
      onModelChange={setModel}
      pack={learn ? null : pack}
      rows={welcome ? 3 : 2}
      placeholder={
        learn
          ? "问问公司的产品、报价方式、制度和竞品，例如：销售提成怎么算？"
          : !canAiWrite
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
            onConfirmRequirement={w.confirmRequirement}
            mode={w.mode}
            onAsk={send}
            prdOpportunity={opp.data ? { id: opp.data.id, name: opp.data.name, canGenerate: canAiWrite } : undefined}
          />
        ) : w.loadingId ? (
          <div className="flex flex-1 items-center justify-center gap-2 text-sm text-zinc-400">
            <Loader2 className="size-4 animate-spin" />
            正在加载会话…
          </div>
        ) : (
          <Welcome
            composer={composer(true)}
            onPick={send}
            readOnly={!canAiWrite}
            mode={w.mode}
            onModeChange={w.switchMode}
          />
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
