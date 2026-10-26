"use client"

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

import { api } from "@/lib/api"
import { DEMO_USERS, getStoredRole, mockLogin, storeRole } from "@/lib/session"
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
}

const SessionContext = createContext<SessionValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [role, setRole] = useState<Role>("sales")

  // 首次挂载：恢复上次的角色；没有 token 时静默登录（core 未启动时忽略错误，由页面显示错误状态）
  useEffect(() => {
    const stored = getStoredRole()
    setRole(stored)
    if (!getToken()) {
      mockLogin(stored)
        .then(() => queryClient.invalidateQueries())
        .catch(() => undefined)
    }
  }, [queryClient])

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
  })
  const userId = me.data && me.data.role === role ? me.data.id : null

  const value = useMemo<SessionValue>(
    () => ({ role, user: DEMO_USERS[role], isLead: role !== "sales", userId, switchRole }),
    [role, userId, switchRole],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error("useSession must be used within SessionProvider")
  return ctx
}
