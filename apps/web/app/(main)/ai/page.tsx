"use client"

import { History, Loader2, Sparkles } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useCallback, useEffect, useRef, useState } from "react"

import { useAiSession, type AiSession } from "@/components/agent/AiSessionProvider"
import { ChatView } from "@/components/agent/ChatView"
import { Composer } from "@/components/agent/Composer"
import { HistorySheet } from "@/components/agent/HistorySheet"
import { Welcome } from "@/components/agent/Welcome"
import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { PageTip } from "@/components/onboarding/PageTip"
import { useOpportunity } from "@/hooks/useOpportunities"
import { usePermissions } from "@/hooks/usePermissions"
import { useDefaultPack, usePackName } from "@/hooks/useProductLines"
import { DEFAULT_PACK_LABEL } from "@/lib/agent-labels"
import type { AgentMode } from "@/lib/agent-mode"
import { takePastedMaterial } from "@/lib/materials"
import { aiThreadHref } from "@/lib/thread-history"
import { PAGE_TIPS } from "@/lib/onboarding"

/**
 * 当前会话与地址 `/ai?t=<id>` 同步（会话记录面板里的链接靠地址通信）：
 * - 地址变了（点会话记录某条 / 点「新对话」/ 刷新）→ 打开对应会话或清空
 * - 从别的页面回到 `/ai`（地址没有 t）而会话还在 → 保留会话，把 id 补回地址
 * - 刷新后打开 `/ai`：回到这个模式上次的对话
 * - 发出第一条消息生成了新会话 → 把 id 写进地址（replace，不多一条历史记录）
 */
function useThreadUrl(w: AiSession): { goNew: () => void; goMode: (mode: AgentMode) => void } {
  const params = useSearchParams()
  const t = params.get("t")
  const prompt = params.get("prompt")
  const opp = params.get("opp")
  const paste = params.get("paste") === "1"
  const autoSend = params.get("send") === "1"
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
    } else if (first && !prompt && !mode) {
      void w.restore()
    }
    // 只跟着地址里的 t 走；prompt / mode 只用来判断是不是从别处带参数进来的
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t])

  // ?prompt=：从客户 / 商机页带过来的上下文，开新对话并预填输入框，然后去掉参数；
  // &send=1（商机「出方案」）直接发出去，等输入框和商机都设好之后的那次渲染再发
  const [pendingSend, setPendingSend] = useState<string | null>(null)
  useEffect(() => {
    if (!pendingSend) return
    const cur = latest.current.w
    if (cur.mode !== "work" || cur.input !== pendingSend || cur.stream.isStreaming) return
    setPendingSend(null)
    cur.send(pendingSend)
  }, [pendingSend, w.input, w.mode, w.opportunityId, w.stream.isStreaming])
  useEffect(() => {
    if (prompt === null) return
    const s = latest.current.w.startIn("work")
    s.setInput(prompt)
    s.setOpportunityId(opp)
    if (autoSend) setPendingSend(prompt)
    // &paste=1：写跟进处粘贴的纪要，作为材料带进来（不自动发送，销售看一眼再发）
    const pasted = paste ? takePastedMaterial() : null
    if (pasted) s.loadMaterial(pasted)
    router.replace("/ai", { scroll: false })
  }, [prompt, opp, paste, autoSend, router])

  // 切换模式：显示那个模式上次的对话（没有就是空白），地址跟着换
  const goMode = useCallback(
    (next: AgentMode) => {
      const id = latest.current.w.switchMode(next)
      router.replace(id ? aiThreadHref(id) : "/ai", { scroll: false })
      // 这个模式还没有对话（例如刚刷新过）：接上它上次的对话
      if (!id) void latest.current.w.restore()
    },
    [router],
  )

  // ?mode=learn / ?mode=work：工作台首页按钮直达某个模式（不新建对话）
  useEffect(() => {
    if (mode === "learn" || mode === "work") goMode(mode)
  }, [mode, goMode])

  const threadId = w.stream.threadId
  useEffect(() => {
    if (threadId && threadId !== latest.current.t) router.replace(aiThreadHref(threadId), { scroll: false })
  }, [threadId, router])

  return { goNew: () => router.push("/ai"), goMode }
}

/** AI 方案工作台：居中会话 + 底部大输入框；会话记录在标题行「历史记录」打开的右侧面板里 */
function AiWorkbench() {
  const w = useAiSession()
  const { stream, input, setInput, model, setModel, title, send } = w
  const { canAiWrite } = usePermissions()
  const { goNew, goMode } = useThreadUrl(w)
  // 从商机进入：显示该商机产品线对应的行业包；否则显示团队默认行业包（管理员在「成员与团队」里给团队设置）
  const opp = useOpportunity(w.opportunityId)
  const packName = usePackName()
  const teamPack = useDefaultPack()
  const pack = opp.data?.product_line
    ? packName(opp.data.product_line.pack)
    : teamPack.data
      ? packName(teamPack.data.pack)
      : DEFAULT_PACK_LABEL
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
            onModeChange={canAiWrite ? goMode : undefined}
            streamingModes={w.streaming}
            onAsk={send}
            prdOpportunity={opp.data ? { id: opp.data.id, name: opp.data.name, canGenerate: canAiWrite } : undefined}
            threadId={stream.threadId}
          />
        ) : w.loadingId ? (
          <div className="flex flex-1 items-center justify-center gap-2 text-sm text-zinc-400">
            <Loader2 className="size-4 animate-spin" />
            正在加载会话…
          </div>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col">
            {canAiWrite ? (
              <PageTip id="ai" className="mx-4 mt-3">
                {PAGE_TIPS.ai}
              </PageTip>
            ) : null}
            <Welcome
              composer={composer(true)}
              onPick={send}
              readOnly={!canAiWrite}
              mode={w.mode}
              onModeChange={goMode}
              streamingModes={w.streaming}
            />
          </div>
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
