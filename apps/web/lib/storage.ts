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
  role: "sp.role",
  sidebar: "sp.sidebar",
} as const

/** 旧版本把 token 存在这里；现在登录态只在 HttpOnly Cookie 里，打开页面时顺手删掉旧值 */
export const LEGACY_TOKEN_KEY = "sp.token"

export function clearLegacyToken(): void {
  if (typeof window !== "undefined") writeStorage(LEGACY_TOKEN_KEY, null)
}
