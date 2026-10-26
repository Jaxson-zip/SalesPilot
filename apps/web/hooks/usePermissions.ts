"use client"

import { useMemo } from "react"

import { useSession } from "@/components/shell/SessionProvider"
import {
  canApprove,
  canConfigurePacks,
  canCreateBusiness,
  canEditRecord,
  canRegisterPayment,
  canUseAiWrite,
  canWriteFollowup,
  isReadOnlyRole,
} from "@/lib/permissions"

/** 把 lib/permissions 的纯函数绑定到当前会话（角色 + 当前用户 id） */
export function usePermissions() {
  const { role, userId } = useSession()
  return useMemo(
    () => ({
      readOnly: isReadOnlyRole(role),
      canCreate: canCreateBusiness(role),
      canFollowup: canWriteFollowup(role),
      canAiWrite: canUseAiWrite(role),
      canApprove: canApprove(role),
      canConfigurePacks: canConfigurePacks(role),
      /** 本人负责的业务记录才能改 */
      canEdit: (ownerId: string | null | undefined) => canEditRecord(role, ownerId, userId),
      canPay: (record?: { status: string }) => canRegisterPayment(role, record),
    }),
    [role, userId],
  )
}
