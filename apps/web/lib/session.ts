import { api, setUnauthorizedHandler } from "@/lib/api"
import { readStorage, setToken, STORAGE_KEYS, writeStorage } from "@/lib/storage"
import type { MockLoginData, Role } from "@/types/api"

/** 演示角色（与原型 USERS 一致） */
export const DEMO_USERS: Record<Role, { name: string; title: string; scope: string }> = {
  sales: { name: "张晨", title: "销售", scope: "本人" },
  manager: { name: "李薇", title: "销售主管", scope: "华南销售组" },
  admin: { name: "周敏", title: "系统管理员", scope: "全公司" },
}

export const ROLES: Role[] = ["sales", "manager", "admin"]

export function isRole(v: string | null | undefined): v is Role {
  return v === "sales" || v === "manager" || v === "admin"
}

export function getStoredRole(): Role {
  const v = typeof window === "undefined" ? null : readStorage(STORAGE_KEYS.role)
  return isRole(v) ? v : "sales"
}

export function storeRole(role: Role): void {
  writeStorage(STORAGE_KEYS.role, role)
}

/** 后端可能返回 token 或 access_token，两种都兼容 */
function pickToken(data: MockLoginData & { access_token?: string }): string | null {
  return data.token ?? data.access_token ?? null
}

/** 演示登录：POST /api/auth/mock-login {role}，token 存 localStorage */
export async function mockLogin(role: Role): Promise<MockLoginData> {
  const data = await api.post<MockLoginData & { access_token?: string }>("/api/auth/mock-login", { role })
  setToken(pickToken(data))
  storeRole(role)
  return data
}

export function logout(): void {
  setToken(null)
}

/** token 失效时用当前角色重新登录一次 */
setUnauthorizedHandler(async () => {
  try {
    setToken(null)
    await mockLogin(getStoredRole())
    return true
  } catch {
    return false
  }
})
