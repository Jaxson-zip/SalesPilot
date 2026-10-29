import { api, setUnauthorizedHandler } from "@/lib/api"
import { readStorage, setToken, STORAGE_KEYS, writeStorage } from "@/lib/storage"
import type { MockLoginData, Role } from "@/types/api"

/** 演示账户（与原型 USERS 一致）；can 是登录页上的一句话说明 */
export const DEMO_USERS: Record<Role, { name: string; title: string; scope: string; can: string }> = {
  sales: { name: "张晨", title: "销售", scope: "本人", can: "客户与商机、AI 出方案报价、跟进、报销、日报" },
  manager: {
    name: "李薇",
    title: "销售主管",
    scope: "华南销售组",
    can: "审批报价和报销、团队看板、登记回款与开票、客户交接",
  },
  admin: {
    name: "周敏",
    title: "系统管理员",
    scope: "全公司",
    can: "行业包、业务规则、知识库、操作日志；业务数据只读",
  },
}

export const LOGIN_PATH = "/login"

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

/** GET /api/auth/options：服务端是否要求访问口令 */
export const fetchAuthOptions = () => api.get<{ access_code_required: boolean }>("/api/auth/options")

/** 演示登录：POST /api/auth/mock-login {role, access_code}，token 存 localStorage；已登录切换账户时带当前 token 即可 */
export async function mockLogin(role: Role, accessCode?: string): Promise<MockLoginData> {
  const data = await api.post<MockLoginData & { access_token?: string }>("/api/auth/mock-login", {
    role,
    access_code: accessCode || undefined,
  })
  setToken(pickToken(data))
  storeRole(role)
  return data
}

export function logout(): void {
  setToken(null)
}

/** 去登录页，登录后回到当前页 */
export function loginUrl(next?: string): string {
  return next && next !== LOGIN_PATH && next !== "/" ? `${LOGIN_PATH}?next=${encodeURIComponent(next)}` : LOGIN_PATH
}

/** token 过期 / 失效：回到登录页重新选演示账户（登录页本身的 401 是口令错误，交给页面显示） */
setUnauthorizedHandler(async () => {
  setToken(null)
  if (typeof window !== "undefined" && window.location.pathname !== LOGIN_PATH) {
    window.location.assign(loginUrl(window.location.pathname + window.location.search))
  }
  return false
})
