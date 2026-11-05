import { api, isApiError, setUnauthorizedHandler } from "@/lib/api"
import { clearLegacyToken, readStorage, STORAGE_KEYS, writeStorage } from "@/lib/storage"
import { ErrorCode, type CurrentUser, type MockLoginData, type Role } from "@/types/api"

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

/** 一键进入的演示账户：每个角色的默认账户 + 华东组（另一个团队、另一个行业包，演示团队之间数据隔离） */
export interface DemoAccount {
  role: Role
  name: string
  title: string
  scope: string
  can: string
  login: string
}

export const DEMO_ACCOUNTS: DemoAccount[] = [
  { role: "sales", ...DEMO_USERS.sales },
  { role: "manager", ...DEMO_USERS.manager },
  { role: "admin", ...DEMO_USERS.admin },
  {
    role: "manager",
    name: "陈静",
    title: "销售主管",
    scope: "华东销售组",
    can: "华东组（软件外包）的审批、团队看板和回款；看不到华南组的数据",
    login: "chenjing",
  },
  {
    role: "sales",
    name: "刘洋",
    title: "销售",
    scope: "华东销售组",
    can: "软件外包：AI 拆功能模块、估人天出报价",
    login: "liuyang",
  },
]

export const ROLE_TITLE: Record<Role, string> = { sales: "销售", manager: "销售主管", admin: "系统管理员" }

/** 左下角显示的当前用户 */
export interface Profile {
  name: string
  title: string
  scope: string
}

export const LOGIN_PATH = "/login"

/** 不需要登录的页面：登录页、发给客户的报价分享页 */
export function isPublicPath(pathname: string | null): boolean {
  return pathname === LOGIN_PATH || Boolean(pathname?.startsWith("/share/"))
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

const PROFILE_KEY = "sp.profile"

export function profileOf(user: CurrentUser): Profile {
  return {
    name: user.name,
    title: user.solo_mode && user.role === "manager" ? "个人模式" : ROLE_TITLE[user.role],
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

/** 登录成功：登录态由 core 写进 HttpOnly Cookie，这里只记角色和左下角显示的用户信息（不含 token） */
function remember(data: MockLoginData): MockLoginData {
  clearLegacyToken()
  if (data.user) {
    storeRole(data.user.role)
    storeProfile(profileOf(data.user))
  }
  return data
}

/** GET /api/auth/options：是否要求访问口令、是否开放演示账户 */
export const fetchAuthOptions = () =>
  api.get<{ access_code_required: boolean; demo_login: boolean }>("/api/auth/options")

/** 演示账户：POST /api/auth/mock-login {role, username?, access_code}；已登录切换账户时浏览器带着登录 Cookie，不用口令 */
export async function mockLogin(role: Role, accessCode?: string, login?: string): Promise<MockLoginData> {
  const data = await api.post<MockLoginData>("/api/auth/mock-login", {
    role,
    username: login,
    access_code: accessCode || undefined,
  })
  storeRole(role)
  return remember(data)
}

/** 账号密码：POST /api/auth/login */
export async function passwordLogin(username: string, password: string, accessCode?: string): Promise<MockLoginData> {
  const data = await api.post<MockLoginData>("/api/auth/login", {
    username,
    password,
    access_code: accessCode || undefined,
  })
  return remember(data)
}

/** 改自己的密码：成功后旧登录全部作废，core 写入新的登录 Cookie */
export async function changePassword(oldPassword: string, newPassword: string): Promise<MockLoginData> {
  const data = await api.post<MockLoginData>("/api/auth/password", {
    old_password: oldPassword,
    new_password: newPassword,
  })
  return remember(data)
}

/** 退出登录：POST /api/auth/logout 让 core 清掉 HttpOnly Cookie（JS 删不掉它）；请求失败也清本地信息 */
export async function logout(): Promise<void> {
  clearLegacyToken()
  storeProfile(null)
  try {
    await api.post<null>("/api/auth/logout")
  } catch {
    // 网络失败时 Cookie 留到过期；本地信息已清，回登录页后重新登录会覆盖
  }
}

/** 去登录页，登录后回到当前页 */
export function loginUrl(next?: string): string {
  return next && next !== LOGIN_PATH && next !== "/" ? `${LOGIN_PATH}?next=${encodeURIComponent(next)}` : LOGIN_PATH
}

/** token 过期 / 失效 / 账号停用：回到登录页（登录页本身的 401 是账号密码或口令错误，交给页面显示） */
setUnauthorizedHandler(async () => {
  clearLegacyToken()
  if (typeof window !== "undefined" && window.location.pathname !== LOGIN_PATH) {
    window.location.assign(loginUrl(window.location.pathname + window.location.search))
  }
  return false
})

/**
 * 登录是否已核实（之后才渲染页面、发业务请求）：/api/me 成功；或失败但不是 401（网络、服务不可用，交给页面显示错误）。
 * 401 和还没开始核实都不算：这时会回登录页，不能让页面先发一批请求（回归：通知、模板、报销三个接口各 401 一次）。
 */
export function sessionVerified(authed: boolean, hasUser: boolean, error: unknown): boolean {
  if (!authed) return false
  if (hasUser) return true
  return error != null && !(isApiError(error) && error.code === ErrorCode.UNAUTHORIZED)
}
