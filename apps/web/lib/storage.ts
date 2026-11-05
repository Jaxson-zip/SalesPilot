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

/** AI 工作台记住的「每个人最近的会话 / 模式」，键为 sp.ai.<userId>.<mode> */
export const AI_SESSION_PREFIX = "sp.ai."

/** 删除某个前缀下的全部键（先收集再删，边遍历边删会跳过元素） */
export function removeByPrefix(store: Pick<Storage, "length" | "key" | "removeItem">, prefix: string): number {
  const keys: string[] = []
  for (let i = 0; i < store.length; i++) {
    const k = store.key(i)
    if (k?.startsWith(prefix)) keys.push(k)
  }
  keys.forEach((k) => store.removeItem(k))
  return keys.length
}

/** 退出登录时清掉 AI 工作台记住的会话：重新登录从新对话开始，共用电脑时下一个人也看不到 */
export function clearAiSessions(): void {
  try {
    if (typeof window !== "undefined") removeByPrefix(window.localStorage, AI_SESSION_PREFIX)
  } catch {
    // 存储不可用时没有可清的
  }
}

export function clearLegacyToken(): void {
  if (typeof window !== "undefined") writeStorage(LEGACY_TOKEN_KEY, null)
}
