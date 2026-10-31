"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { joinSpeech, recognitionCtor, speechErrorText, transcriptOf, type RecognitionLike } from "@/lib/speech"

/**
 * 输入框的语音输入：开始时记下已有内容，边说边把识别结果接在后面（临时结果也实时显示），再点一次停止。
 * supported 挂载后才判断（服务端渲染时没有 window），不支持的浏览器不显示按钮。
 */
export function useSpeechInput(value: string, onChange: (next: string) => void) {
  const [supported, setSupported] = useState(false)
  const [listening, setListening] = useState(false)
  const rec = useRef<RecognitionLike | null>(null)
  const latest = useRef({ value, onChange })
  latest.current = { value, onChange }

  useEffect(() => {
    setSupported(recognitionCtor(window) !== null)
    return () => rec.current?.abort()
  }, [])

  const start = useCallback(() => {
    const Ctor = recognitionCtor(window)
    if (!Ctor) return
    const r = new Ctor()
    const base = latest.current.value
    r.lang = "zh-CN"
    r.continuous = true
    r.interimResults = true
    r.onresult = (e) => latest.current.onChange(joinSpeech(base, transcriptOf(e)))
    r.onerror = (e) => {
      const text = speechErrorText(e.error)
      if (text) toast.error(text)
    }
    r.onend = () => {
      rec.current = null
      setListening(false)
    }
    rec.current = r
    try {
      r.start()
      setListening(true)
    } catch {
      rec.current = null
      toast.error("语音识别没能启动，请稍后再试")
    }
  }, [])

  const toggle = useCallback(() => {
    if (rec.current) rec.current.stop()
    else start()
  }, [start])

  return { supported, listening, toggle }
}
