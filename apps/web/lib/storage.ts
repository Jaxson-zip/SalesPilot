/** localStorage 读写：隐私模式 / 禁用存储时会抛异常，这里统一吞掉 */
export function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    // 存储不可用时静默降级（只影响偏好记忆）
  }
}

export const STORAGE_KEYS = {
  token: "sp.token",
  role: "sp.role",
  sidebar: "sp.sidebar",
  aiHistory: "sp.aiHistory",
} as const

export function getToken(): string | null {
  if (typeof window === "undefined") return null
  return readStorage(STORAGE_KEYS.token)
}

export function setToken(token: string | null): void {
  writeStorage(STORAGE_KEYS.token, token)
}
