"use client"

import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"

import { Locked } from "@/components/biz/EmptyState"
import { useSession } from "@/components/shell/SessionProvider"
import { fetchAuthOptions } from "@/lib/session"
import type { Role } from "@/types/api"

/** 只有演示环境（DEMO_LOGIN=true）左下角才有「切换演示账户」，正式环境不提示 */
export const DEMO_SWITCH_HINT = "，可在左下角切换演示账户查看"

/** 前端只做展示层面的隐藏；真正的权限由 core service 层过滤（规则 4） */
export function RoleGate({
  roles,
  config = false,
  lockedText,
  children,
}: {
  roles: Role[]
  /** 系统配置页：个人模式下主管也能进（与 core can_configure 一致） */
  config?: boolean
  lockedText: string
  children: ReactNode
}) {
  const { role, canConfigure } = useSession()
  const options = useQuery({ queryKey: ["auth", "options"], queryFn: fetchAuthOptions, staleTime: 5 * 60_000 })
  const allowed = roles.includes(role) || (config && canConfigure)
  if (allowed) return <>{children}</>
  const demo = options.data?.demo_login ?? false
  return <Locked description={demo ? `${lockedText}${DEMO_SWITCH_HINT}` : lockedText} />
}
