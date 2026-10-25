"use client"

import type { ReactNode } from "react"

import { Locked } from "@/components/biz/EmptyState"
import { useSession } from "@/components/shell/SessionProvider"
import type { Role } from "@/types/api"

/** 前端只做展示层面的隐藏；真正的权限由 core service 层过滤（规则 4） */
export function RoleGate({ roles, lockedText, children }: { roles: Role[]; lockedText: string; children: ReactNode }) {
  const { role } = useSession()
  return roles.includes(role) ? <>{children}</> : <Locked description={lockedText} />
}
