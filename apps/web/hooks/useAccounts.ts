"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"
import type { Role } from "@/types/api"

/** GET /api/admin/users（仅管理员） */
export interface AccountItem {
  id: string
  username: string | null
  name: string
  role: Role
  team_id: string | null
  team_name: string | null
  active: boolean
  /** 新建 / 重置密码后还没改过密码 */
  must_change_password: boolean
  last_login_at: string | null
  /** 名下客户数：停用后还有客户要提醒主管交接 */
  customers: number
}

export interface AccountCreate {
  username: string
  name: string
  role: Role
  team_id?: string | null
}

export interface AccountUpdate {
  name?: string
  role?: Role
  team_id?: string | null
  active?: boolean
}

/** 新建成员 / 重置密码：临时密码只返回这一次 */
export interface TempPassword {
  account: AccountItem
  temp_password: string
}

export interface TeamItem {
  id: string
  name: string
  members: number
  managers: string[]
  /** 团队默认产品线：成员不从商机进入 AI 时用它对应的行业包；没设时用系统默认行业包 */
  default_product_line_id: string | null
  default_product_line: string | null
  /** 默认产品线对应的行业包 id */
  pack: string | null
}

export interface TeamIn {
  name: string
  /** 不传 = 不改；null = 改回系统默认行业包 */
  default_product_line_id?: string | null
}

const KEYS = { users: ["admin", "users"] as const, teams: ["admin", "teams"] as const }

export function useAccounts() {
  return useQuery({
    queryKey: KEYS.users,
    queryFn: ({ signal }) => api.get<AccountItem[]>("/api/admin/users", undefined, signal),
  })
}

export function useTeams() {
  return useQuery({
    queryKey: KEYS.teams,
    queryFn: ({ signal }) => api.get<TeamItem[]>("/api/admin/teams", undefined, signal),
  })
}

/** 改了成员之后，成员列表、团队人数、同事下拉都要刷新 */
function useRefresh() {
  const qc = useQueryClient()
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: KEYS.users }),
      qc.invalidateQueries({ queryKey: KEYS.teams }),
      qc.invalidateQueries({ queryKey: ["users"] }),
    ])
}

export function useCreateAccount() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: AccountCreate) => api.post<TempPassword>("/api/admin/users", body),
    onSuccess: () => refresh(),
    onError: notifyError,
  })
}

export function useUpdateAccount() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: AccountUpdate }) =>
      api.patch<AccountItem>(`/api/admin/users/${id}`, body),
    onSuccess: () => refresh(),
    onError: notifyError,
  })
}

export function useResetPassword() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (id: string) => api.post<TempPassword>(`/api/admin/users/${id}/reset-password`),
    onSuccess: () => refresh(),
    onError: notifyError,
  })
}

export function useSaveTeam() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ id, ...body }: TeamIn & { id?: string }) =>
      id ? api.patch<TeamItem>(`/api/admin/teams/${id}`, body) : api.post<TeamItem>("/api/admin/teams", body),
    onSuccess: (team, { id }) => {
      toast.success(id ? "已保存团队设置" : `已新建团队「${team.name}」`)
      return refresh()
    },
    onError: notifyError,
  })
}
