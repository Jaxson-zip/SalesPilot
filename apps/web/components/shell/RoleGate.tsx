"use client"

import type { ReactNode } from "react"

import { Locked } from "@/components/biz/EmptyState"
import { useSession } from "@/components/shell/SessionProvider"
import type { Role } from "@/types/api"

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
  const allowed = roles.includes(role) || (config && canConfigure)
  return allowed ? <>{children}</> : <Locked description={lockedText} />
}
