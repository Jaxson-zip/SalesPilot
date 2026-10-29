"use client"

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { usePathname, useRouter } from "next/navigation"
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

import { api } from "@/lib/api"
import { DEMO_USERS, getStoredRole, LOGIN_PATH, loginUrl, logout, mockLogin, storeRole } from "@/lib/session"
import { getToken } from "@/lib/storage"
import type { CurrentUser, Role } from "@/types/api"

interface SessionValue {
  role: Role
  user: (typeof DEMO_USERS)[Role]
  isLead: boolean
  /** 当前用户 id（GET /api/me；加载中或与当前角色不一致时为 null，用于判断「本人的记录」） */
  userId: string | null
  /** 切换演示角色：重新 mock 登录并刷新所有查询 */
  switchRole: (role: Role) => Promise<void>
  /** 登录页：选演示账户（+ 访问口令）登录 */
  signIn: (role: Role, accessCode?: string) => Promise<void>
  /** 退出登录，回到登录页 */
  signOut: () => void
}

const SessionContext = createContext<SessionValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const router = useRouter()
  const pathname = usePathname()
  const [role, setRole] = useState<Role>("sales")
  const [authed, setAuthed] = useState(false)

  // 恢复上次的角色；没有 token 时去登录页选演示账户
  useEffect(() => {
    setRole(getStoredRole())
    const has = Boolean(getToken())
    setAuthed(has)
    if (!has && pathname !== LOGIN_PATH) router.replace(loginUrl(window.location.pathname + window.location.search))
  }, [pathname, router])

  const signIn = useCallback(
    async (next: Role, accessCode?: string) => {
      await mockLogin(next, accessCode)
      setRole(next)
      setAuthed(true)
      queryClient.clear()
    },
    [queryClient],
  )

  // 整页跳转：丢掉所有缓存和进行中的请求，避免它们 401 后又带着 next 跳一次
  const signOut = useCallback(() => {
    logout()
    window.location.assign(LOGIN_PATH)
  }, [])

  const switchRole = useCallback(
    async (next: Role) => {
      setRole(next)
      storeRole(next)
      try {
        await mockLogin(next)
      } finally {
        await queryClient.invalidateQueries()
      }
    },
    [queryClient],
  )

  // 切换角色后 invalidateQueries 会用新 token 重新拉取；角色对不上的旧结果不采用
  const me = useQuery({
    queryKey: ["me", role],
    queryFn: ({ signal }) => api.get<CurrentUser>("/api/me", undefined, signal),
    staleTime: 5 * 60_000,
    enabled: authed,
  })
  const userId = me.data && me.data.role === role ? me.data.id : null

  const value = useMemo<SessionValue>(
    () => ({ role, user: DEMO_USERS[role], isLead: role !== "sales", userId, switchRole, signIn, signOut }),
    [role, userId, switchRole, signIn, signOut],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error("useSession must be used within SessionProvider")
  return ctx
}
