"use client"

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { usePathname, useRouter } from "next/navigation"
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react"

import { api } from "@/lib/api"
import {
  changePassword as postPassword,
  DEMO_USERS,
  getStoredProfile,
  getStoredRole,
  isPublicPath,
  LOGIN_PATH,
  loginUrl,
  logout,
  mockLogin,
  passwordLogin,
  profileOf,
  storeProfile,
  storeRole,
  type Profile,
} from "@/lib/session"
import { canConfigurePacks } from "@/lib/permissions"
import { getToken } from "@/lib/storage"
import type { CurrentUser, Role } from "@/types/api"

interface SessionValue {
  role: Role
  /** 左下角显示的当前用户（姓名、角色、团队） */
  user: Profile
  isLead: boolean
  /** 当前用户 id（GET /api/me；加载中或与当前角色不一致时为 null，用于判断「本人的记录」） */
  userId: string | null
  /** 管理员新建 / 重置密码后，登录要先改密码 */
  mustChangePassword: boolean
  /** 个人模式：一个人接单，隐藏团队相关页面 */
  solo: boolean
  /** 能改系统配置（管理员；个人模式下的主管） */
  canConfigure: boolean
  /** 切换演示账户：重新 mock 登录并刷新所有查询 */
  switchRole: (role: Role) => Promise<void>
  /** 登录页：演示账户一键进入 */
  signIn: (role: Role, accessCode?: string) => Promise<void>
  /** 登录页：账号密码登录 */
  signInWithPassword: (username: string, password: string, accessCode?: string) => Promise<void>
  /** 改自己的密码（换成新 token） */
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>
  /** 退出登录，回到登录页 */
  signOut: () => void
}

const SessionContext = createContext<SessionValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const router = useRouter()
  const pathname = usePathname()
  const [role, setRole] = useState<Role>("sales")
  const [stored, setStored] = useState<Profile | null>(null)
  const [authed, setAuthed] = useState(false)
  const switching = useRef(false)

  // 恢复上次的角色和用户；没有 token 时去登录页
  useEffect(() => {
    setRole(getStoredRole())
    setStored(getStoredProfile())
    const has = Boolean(getToken())
    setAuthed(has)
    if (!has && !isPublicPath(pathname)) router.replace(loginUrl(window.location.pathname + window.location.search))
  }, [pathname, router])

  const enter = useCallback(
    (user: CurrentUser | undefined, fallback: Role) => {
      setRole(user?.role ?? fallback)
      setStored(user ? profileOf(user) : null)
      setAuthed(true)
      queryClient.clear()
    },
    [queryClient],
  )

  const signIn = useCallback(
    async (next: Role, accessCode?: string) => enter((await mockLogin(next, accessCode)).user, next),
    [enter],
  )

  const signInWithPassword = useCallback(
    async (username: string, password: string, accessCode?: string) => {
      const data = await passwordLogin(username, password, accessCode)
      enter(data.user, data.user?.role ?? "sales")
    },
    [enter],
  )

  const changePassword = useCallback(
    async (oldPassword: string, newPassword: string) => {
      await postPassword(oldPassword, newPassword)
      await queryClient.invalidateQueries({ queryKey: ["me"] })
    },
    [queryClient],
  )

  // 整页跳转：丢掉所有缓存和进行中的请求，避免它们 401 后又带着 next 跳一次
  const signOut = useCallback(() => {
    logout()
    window.location.assign(LOGIN_PATH)
  }, [])

  // 先换到新 token 再切角色，避免用旧 token 拉到旧角色的 /api/me
  const switchRole = useCallback(
    async (next: Role) => {
      switching.current = true
      try {
        const data = await mockLogin(next)
        setRole(next)
        setStored(data.user ? profileOf(data.user) : null)
      } finally {
        switching.current = false
        await queryClient.invalidateQueries()
      }
    },
    [queryClient],
  )

  const me = useQuery({
    queryKey: ["me", role],
    queryFn: ({ signal }) => api.get<CurrentUser>("/api/me", undefined, signal),
    staleTime: 5 * 60_000,
    enabled: authed,
  })

  // 管理员改了角色：以服务端为准
  const serverRole = me.data?.role
  useEffect(() => {
    if (serverRole && serverRole !== role && !switching.current) {
      setRole(serverRole)
      storeRole(serverRole)
    }
  }, [serverRole, role])

  const fresh = me.data && me.data.role === role ? me.data : null
  useEffect(() => {
    if (fresh) storeProfile(profileOf(fresh))
  }, [fresh])

  const userId = fresh?.id ?? null
  const user = fresh ? profileOf(fresh) : (stored ?? DEMO_USERS[role])
  const mustChangePassword = Boolean(fresh?.must_change_password)
  const solo = Boolean(fresh?.solo_mode)
  const canConfigure = canConfigurePacks(role, solo)
  const name = user.name
  const title = user.title
  const scope = user.scope

  const value = useMemo<SessionValue>(
    () => ({
      role,
      user: { name, title, scope },
      isLead: role !== "sales",
      userId,
      mustChangePassword,
      solo,
      canConfigure,
      switchRole,
      signIn,
      signInWithPassword,
      changePassword,
      signOut,
    }),
    [
      role,
      name,
      title,
      scope,
      userId,
      mustChangePassword,
      solo,
      canConfigure,
      switchRole,
      signIn,
      signInWithPassword,
      changePassword,
      signOut,
    ],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error("useSession must be used within SessionProvider")
  return ctx
}
