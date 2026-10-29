"use client"

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"

import { notifyError } from "@/hooks/notify"
import { api, isAbortError } from "@/lib/api"
import { isPrd, type Prd } from "@/lib/prd"
import { postSSE } from "@/lib/sse"

export const prdKey = (oppId: string) => ["opportunities", oppId, "prd"] as const

const prdPath = (oppId: string) => `/api/opportunities/${oppId}/requirement/prd`

/** 已生成的 PRD（没生成过为 null） */
export function usePrd(oppId: string, enabled = true) {
  return useQuery({
    queryKey: prdKey(oppId),
    queryFn: ({ signal }) => api.get<Prd | null>(prdPath(oppId), undefined, signal),
    enabled: enabled && Boolean(oppId),
  })
}

/**
 * 生成 / 重新生成（SSE）：正文逐字出现在 draft，结束时用服务端保存的全文刷新缓存。
 * 关闭弹窗（组件卸载）时中止请求；服务端没收到结束就不会保存。
 */
export function useGeneratePrd(oppId: string) {
  const qc = useQueryClient()
  const [draft, setDraft] = useState("")
  const [running, setRunning] = useState(false)
  const abort = useRef<AbortController | null>(null)

  useEffect(() => () => abort.current?.abort(), [])

  const generate = async () => {
    if (abort.current) return
    const ctrl = new AbortController()
    abort.current = ctrl
    setDraft("")
    setRunning(true)
    try {
      await postSSE(
        prdPath(oppId),
        {},
        {
          signal: ctrl.signal,
          onEvent: (e) => {
            if (e.event === "message.delta") setDraft((t) => t + e.data.text)
            else if (e.event === "artifact" && e.data.type === "prd" && isPrd(e.data.data)) {
              qc.setQueryData(prdKey(oppId), e.data.data)
              setDraft("")
            } else if (e.event === "error") notifyError(new Error(e.data.message))
          },
        },
      )
    } catch (err) {
      if (!isAbortError(err)) notifyError(err)
    } finally {
      abort.current = null
      setRunning(false)
    }
  }

  return { draft, running, generate }
}
