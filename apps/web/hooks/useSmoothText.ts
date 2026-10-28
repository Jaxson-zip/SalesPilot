"use client"

import { useEffect, useState } from "react"

/**
 * 平滑显示流式文字：模型常常一次吐出一大段（或模板回复整段到达），直接渲染会「一下子全出来」。
 * 这里按帧逐步追上已收到的文字，积压越多追得越快（约 1/15 每帧，至少 1 个字）。
 * `animate` 只在首次渲染时生效：从历史加载的消息直接完整显示。
 */
export function useSmoothText(text: string, animate: boolean): string {
  const [shown, setShown] = useState(() => (animate ? 0 : text.length))
  const target = text.length

  useEffect(() => {
    if (shown >= target) return
    const id = requestAnimationFrame(() =>
      setShown((n) => Math.min(target, n + Math.max(1, Math.ceil((target - n) / 15)))),
    )
    return () => cancelAnimationFrame(id)
  }, [shown, target])

  return shown >= target ? text : text.slice(0, shown)
}
