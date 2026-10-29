import { api, setUnauthorizedHandler } from "@/lib/api"
import { readStorage, setToken, STORAGE_KEYS, writeStorage } from "@/lib/storage"
import type { CurrentUser, MockLoginData, Role } from "@/types/api"

/** 演示账户（与原型 USERS 一致）；can 是登录页上的一句话说明，login 是登录名 */
export const DEMO_USERS: Record<Role, { name: string; title: string; scope: string; can: string; login: string }> = {
  sales: {
    name: "张晨",
    title: "销售",
    scope: "本人",
    can: "客户与商机、AI 出方案报价、跟进、报销、日报",
    login: "zhangchen",
  },
  manager: {
    name: "李薇",
    title: "销售主管",
    scope: "华南销售组",
    can: "审批报价和报销、团队看板、登记回款与开票、客户交接",
    login: "liwei",
  },
  admin: {
    name: "周敏",
    title: "系统管理员",
    scope: "全公司",
    can: "成员与团队、行业包、业务规则、知识库、操作日志；业务数据只读",
    login: "zhoumin",
  },
}

export const ROLE_TITLE: Record<Role, string> = { sales: "销售", manager: "销售主管", admin: "系统管理员" }

/** 左下角显示的当前用户 */
export interface Profile {
  name: string
  title: string
  scope: string
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

const PROFILE_KEY = "sp.profile"

export function profileOf(user: CurrentUser): Profile {
  return {
    name: user.name,
    title: ROLE_TITLE[user.role],
    scope: user.team_name ?? (user.role === "admin" ? "全公司" : ""),
  }
}

/** 上次登录的用户信息：刷新页面时先显示，等 /api/me 回来再更新 */
export function getStoredProfile(): Profile | null {
  try {
    const raw = readStorage(PROFILE_KEY)
    return raw ? (JSON.parse(raw) as Profile) : null
  } catch {
    return null
  }
}

export function storeProfile(profile: Profile | null): void {
  writeStorage(PROFILE_KEY, profile ? JSON.stringify(profile) : null)
}

/** 后端可能返回 token 或 access_token，两种都兼容 */
function pickToken(data: MockLoginData & { access_token?: string }): string | null {
  return data.token ?? data.access_token ?? null
}

function remember(data: MockLoginData & { access_token?: string }): MockLoginData {
  setToken(pickToken(data))
  if (data.user) {
    storeRole(data.user.role)
    storeProfile(profileOf(data.user))
  }
  return data
}

/** GET /api/auth/options：是否要求访问口令、是否开放演示账户 */
export const fetchAuthOptions = () =>
  api.get<{ access_code_required: boolean; demo_login: boolean }>("/api/auth/options")

/** 演示账户：POST /api/auth/mock-login {role, access_code}；已登录切换账户时带当前 token 即可 */
export async function mockLogin(role: Role, accessCode?: string): Promise<MockLoginData> {
  const data = await api.post<MockLoginData & { access_token?: string }>("/api/auth/mock-login", {
    role,
    access_code: accessCode || undefined,
  })
  storeRole(role)
  return remember(data)
}

/** 账号密码：POST /api/auth/login */
export async function passwordLogin(username: string, password: string, accessCode?: string): Promise<MockLoginData> {
  const data = await api.post<MockLoginData & { access_token?: string }>("/api/auth/login", {
    username,
    password,
    access_code: accessCode || undefined,
  })
  return remember(data)
}

/** 改自己的密码：成功后旧 token 作废，换成返回的新 token */
export async function changePassword(oldPassword: string, newPassword: string): Promise<MockLoginData> {
  const data = await api.post<MockLoginData & { access_token?: string }>("/api/auth/password", {
    old_password: oldPassword,
    new_password: newPassword,
  })
  return remember(data)
}

export function logout(): void {
  setToken(null)
  storeProfile(null)
}

/** 去登录页，登录后回到当前页 */
export function loginUrl(next?: string): string {
  return next && next !== LOGIN_PATH && next !== "/" ? `${LOGIN_PATH}?next=${encodeURIComponent(next)}` : LOGIN_PATH
}

/** token 过期 / 失效 / 账号停用：回到登录页（登录页本身的 401 是账号密码或口令错误，交给页面显示） */
setUnauthorizedHandler(async () => {
  setToken(null)
  if (typeof window !== "undefined" && window.location.pathname !== LOGIN_PATH) {
    window.location.assign(loginUrl(window.location.pathname + window.location.search))
  }
  return false
})
