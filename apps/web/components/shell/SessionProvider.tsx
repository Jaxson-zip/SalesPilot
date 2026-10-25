"use client"

import { useQueryClient } from "@tanstack/react-query"
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

import { DEMO_USERS, getStoredRole, mockLogin, storeRole } from "@/lib/session"
import { getToken } from "@/lib/storage"
import type { Role } from "@/types/api"

interface SessionValue {
  role: Role
  user: (typeof DEMO_USERS)[Role]
  isLead: boolean
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

  const value = useMemo<SessionValue>(
    () => ({ role, user: DEMO_USERS[role], isLead: role !== "sales", switchRole }),
    [role, switchRole],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error("useSession must be used within SessionProvider")
  return ctx
}
