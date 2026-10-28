"use client"

import { useCallback, useEffect, useState } from "react"

import { readStorage, STORAGE_KEYS, writeStorage } from "@/lib/storage"

const MD_QUERY = "(min-width: 768px)"
const XL_QUERY = "(min-width: 1280px)"

/**
 * AI 工作台会话记录栏的显示状态（与左侧导航栏同一套规则）：
 * - ≥768：栏固定在左侧，可以收起；手动切换过 → 记住偏好（`sp.aiHistory`），
 *   没有偏好 → ≥1280 展开，768–1279 收起（避免导航栏 + 会话栏把对话区挤窄）
 * - <768：浮层，默认关闭；选中会话 / 新对话 / 点遮罩 / Esc 后关闭
 */
export function useHistoryPanel() {
  const [pinned, setPinnedState] = useState(true)
  const [overlay, setOverlay] = useState(false)

  useEffect(() => {
    const xl = window.matchMedia(XL_QUERY)
    const apply = () => {
      const pref = readStorage(STORAGE_KEYS.aiHistory)
      setPinnedState(pref === "expanded" || pref === "collapsed" ? pref === "expanded" : xl.matches)
    }
    apply()
    xl.addEventListener("change", apply)
    return () => xl.removeEventListener("change", apply)
  }, [])

  useEffect(() => {
    if (!overlay) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOverlay(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [overlay])

  const toggle = useCallback(() => {
    if (window.matchMedia(MD_QUERY).matches) {
      setPinnedState((p) => {
        writeStorage(STORAGE_KEYS.aiHistory, p ? "collapsed" : "expanded")
        return !p
      })
    } else {
      setOverlay((o) => !o)
    }
  }, [])

  const closeOverlay = useCallback(() => setOverlay(false), [])

  return { pinned, overlay, toggle, closeOverlay }
}
