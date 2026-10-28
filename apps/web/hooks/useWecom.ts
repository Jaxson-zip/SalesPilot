"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"

export type WecomEvent = "approval_pending" | "deal_won" | "report_summary" | "report_remind"

export interface WecomPush {
  at: string
  event: string
  title: string
  ok: boolean
  error?: string | null
}

export interface WecomConfig {
  configured: boolean
  source: "web" | "env" | "none"
  webhook_masked?: string | null
  enabled: boolean
  events: string[]
  options: { key: string; label: string }[]
  recent: WecomPush[]
  web_base_url: string
}

export interface WecomConfigInput {
  webhook_url?: string | null
  enabled: boolean
  events: string[]
}

export interface PushResult {
  ok: boolean
  error?: string | null
}

const KEY = ["integrations", "wecom"] as const
const FLAGS = ["integrations", "flags"] as const

/** GET /api/integrations/wecom（管理员） */
export function useWecomConfig() {
  return useQuery({
    queryKey: KEY,
    queryFn: ({ signal }) => api.get<WecomConfig>("/api/integrations/wecom", undefined, signal),
  })
}

export function useSaveWecom() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: WecomConfigInput) => api.put<WecomConfig>("/api/integrations/wecom", body),
    onSuccess: (data) => {
      qc.setQueryData(KEY, data)
      void qc.invalidateQueries({ queryKey: FLAGS })
      toast.success("推送配置已保存")
    },
    onError: notifyError,
  })
}

/** 推送结果统一提示：企业微信拒绝时显示原因 */
function notifyPush(r: PushResult, okText: string) {
  if (r.ok) toast.success(okText)
  else toast.error(r.error ?? "推送失败")
}

export function useWecomTest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<PushResult>("/api/integrations/wecom/test"),
    onSuccess: (r) => {
      notifyPush(r, "测试消息已发送，请在群里查看")
      void qc.invalidateQueries({ queryKey: KEY })
    },
    onError: notifyError,
  })
}

/** GET /api/integrations/flags：各推送事件是否可用（所有角色） */
export function usePushFlags() {
  return useQuery({
    queryKey: FLAGS,
    queryFn: ({ signal }) => api.get<Record<WecomEvent, boolean>>("/api/integrations/flags", undefined, signal),
    staleTime: 60_000,
  })
}

/** 主管：把团队汇总推到群 */
export function usePushSummary() {
  return useMutation({
    mutationFn: (content: string) => api.post<PushResult>("/api/reports/team/push", { content }),
    onSuccess: (r) => notifyPush(r, "已推送到企业微信群"),
    onError: notifyError,
  })
}

/** 主管：在群里提醒当天未提交日报的人 */
export function useRemindReports() {
  return useMutation({
    mutationFn: (date: string) => api.post<PushResult>("/api/reports/team/remind", { date }),
    onSuccess: (r) => notifyPush(r, "已在企业微信群里提醒"),
    onError: notifyError,
  })
}
