"use client"

import { useEffect, useState } from "react"

/** 值稳定 delay 毫秒后才更新（用于实时制度校验，避免每次按键都请求） */
export function useDebounced<T>(value: T, delay = 400): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return v
}
