"use client"

import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { threadKeys } from "@/hooks/useAgentThreads"
import { useAgentStream } from "@/hooks/useAgentStream"
import { requirementKey } from "@/hooks/useRequirement"
import { DEFAULT_MODEL } from "@/lib/agent-labels"
import type { AgentMode } from "@/lib/agent-mode"
import { extractMaterial, type MaterialOut } from "@/lib/materials"
import {
  MAX_SAMPLES,
  SAMPLE_CONCURRENCY,
  analyzeSample,
  runQueue,
  samplesBusy,
  toSamplesIn,
  type SampleState,
} from "@/lib/samples"
import { lastUserText, messagesToTurns, type ThreadMessages } from "@/lib/thread-history"

/**
 * 一种模式（做方案 / 学习问答）的 AI 会话：输入框、模型、当前会话。
 * AiSessionProvider 给两种模式各建一个，挂在整个应用外壳上（不随页面卸载）：
 * 生成到一半切去别的页面或另一种模式，这边在后台接着输出，回来还在。
 */
export function useAiWorkbench(mode: AgentMode) {
  const stream = useAgentStream()
  const qc = useQueryClient()
  const [input, setInput] = useState("")
  const [model, setModel] = useState(DEFAULT_MODEL)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [material, setMaterial] = useState<MaterialOut | null>(null)
  const [uploading, setUploading] = useState(false)
  const [samples, setSamples] = useState<SampleState | null>(null)
  // 每批样例一个编号：清除或重新选择后，上一批还没回来的结果直接丢弃
  const sampleBatch = useRef(0)
  // 从商机「出方案」进入时关联的商机；新对话 / 打开历史会话时清空
  const [opportunityId, setOpportunityId] = useState<string | null>(null)
  const learning = mode === "learn"

  /** 上传材料：服务端解析成文字（不入库），发送时随消息一起交给 AI */
  const attach = async (file: File) => {
    setUploading(true)
    try {
      setMaterial(await extractMaterial(file))
      clearSamples()
    } catch (err) {
      notifyError(err)
    } finally {
      setUploading(false)
    }
  }

  /** 识别一批样例图片（限量并发，逐张更新进度）；只提示第一条错误，避免几十条重复提示 */
  const recognize = async (files: File[], batch: number) => {
    let reported = false
    await runQueue(files, analyzeSample, SAMPLE_CONCURRENCY, (file, result) => {
      if (sampleBatch.current !== batch) return
      if (result instanceof Error && !reported) {
        reported = true
        notifyError(result)
      }
      setSamples((s) =>
        s
          ? {
              ...s,
              done: s.done + 1,
              items: result instanceof Error ? s.items : [...s.items, result],
              failed: result instanceof Error ? [...s.failed, file] : s.failed,
            }
          : s,
      )
    })
  }

  /** 选择客户样例图片：超过上限只取前 MAX_SAMPLES 张；与「上传材料」二选一 */
  const attachSamples = (picked: File[]) => {
    const files = picked.slice(0, MAX_SAMPLES)
    if (files.length === 0) return
    if (picked.length > MAX_SAMPLES) toast.warning(`一次最多 ${MAX_SAMPLES} 张，只取了前 ${MAX_SAMPLES} 张`)
    const batch = ++sampleBatch.current
    setMaterial(null)
    setSamples({ total: files.length, done: 0, items: [], failed: [] })
    void recognize(files, batch)
  }

  /** 重试识别失败的图片 */
  const retrySamples = () => {
    if (!samples || samplesBusy(samples) || samples.failed.length === 0) return
    const files = samples.failed
    setSamples({ ...samples, done: samples.done - files.length, failed: [] })
    void recognize(files, sampleBatch.current)
  }

  const clearSamples = () => {
    sampleBatch.current++
    setSamples(null)
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
    // 学习问答只问不做：不带材料、样例和商机
    const sampleSet = learning ? null : toSamplesIn(samples)
    const mat = material && !learning ? { name: material.name, text: material.text } : null
    if ((!msg && !mat && !sampleSet) || stream.isStreaming || samplesBusy(samples)) return
    stream.send(msg, model, mat, learning ? null : opportunityId, null, sampleSet, mode)
    setInput("")
    setMaterial(null)
    clearSamples()
  }

  /** 需求卡片「确认需求，出报价」：把核对后的需求随消息提交 */
  const confirmRequirement = (requirement: Record<string, unknown>) => {
    if (stream.isStreaming) return
    stream.send("需求已确认，出正式报价", model, null, opportunityId, requirement, null, mode)
  }

  const newChat = () => {
    stream.reset()
    setInput("")
    setMaterial(null)
    clearSamples()
    setOpportunityId(null)
  }

  /** 显示一条历史会话（provider 已取到消息并按会话的模式分到这里） */
  const show = (id: string, data: ThreadMessages) => {
    const turns = messagesToTurns(data)
    setOpportunityId(learning ? null : (data.opportunity_id ?? null))
    // 这一轮还在后台生成（例如刷新了页面）：先显示之前的内容，再接上本轮
    if (data.running) stream.attach(id, turns, data.running, model)
    else stream.load(id, turns, lastUserText(turns), model)
    setInput("")
  }

  /** 取消息时显示「正在加载会话…」 */
  const loading = async <T>(id: string, task: () => Promise<T>): Promise<T> => {
    setLoadingId(id)
    try {
      return await task()
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
    /** 带入一份已有文字的材料（写跟进处粘贴的纪要） */
    loadMaterial: (m: MaterialOut) => {
      setMaterial(m)
      clearSamples()
    },
    samples,
    attachSamples,
    retrySamples,
    clearSamples,
    title,
    send,
    confirmRequirement,
    newChat,
    show,
    loading,
    opportunityId,
    setOpportunityId,
    mode,
  }
}
