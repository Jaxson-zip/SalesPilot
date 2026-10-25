"use client"

import { useCallback, useEffect, useState } from "react"

import { readStorage, STORAGE_KEYS, writeStorage } from "@/lib/storage"

type Pref = "expanded" | "collapsed"

const XL_QUERY = "(min-width: 1280px)"

function readPref(): Pref | null {
  const v = readStorage(STORAGE_KEYS.sidebar)
  return v === "expanded" || v === "collapsed" ? v : null
}

/**
 * 侧边栏展开状态（§10.4 响应式与侧边栏）：
 * - 用户手动切换过 → 用记住的偏好（localStorage `sp.sidebar`）
 * - 没有偏好 → ≥1280 展开，1024–1279 收起为图标栏
 * - 只在跨过 1280 断点时重新计算（matchMedia change），拖动窗口时不反复重绘
 * <1024 的抽屉由 shadcn Sidebar 自己处理（openMobile）。
 */
export function useSidebarPreference(): [boolean, (open: boolean) => void] {
  const [open, setOpenState] = useState(true)

  useEffect(() => {
    const mql = window.matchMedia(XL_QUERY)
    const apply = () => {
      const pref = readPref()
      setOpenState(pref ? pref === "expanded" : mql.matches)
    }
    apply()
    mql.addEventListener("change", apply)
    return () => mql.removeEventListener("change", apply)
  }, [])

  const setOpen = useCallback((value: boolean) => {
    writeStorage(STORAGE_KEYS.sidebar, value ? "expanded" : "collapsed")
    setOpenState(value)
  }, [])

  return [open, setOpen]
}
