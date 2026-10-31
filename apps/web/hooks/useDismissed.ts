"use client"

import { useCallback, useEffect, useState } from "react"

import { readStorage, writeStorage } from "@/lib/storage"

/**
 * 「关掉就不再显示」的本地开关（localStorage）。挂载前返回 null，避免服务端渲染和首屏闪一下。
 */
export function useDismissed(key: string): [boolean | null, () => void] {
  const [dismissed, setDismissed] = useState<boolean | null>(null)
  useEffect(() => setDismissed(readStorage(key) === "1"), [key])
  const dismiss = useCallback(() => {
    writeStorage(key, "1")
    setDismissed(true)
  }, [key])
  return [dismissed, dismiss]
}
