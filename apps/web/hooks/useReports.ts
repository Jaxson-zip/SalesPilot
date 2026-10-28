"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"

export type ReportStatus = "none" | "draft" | "submitted"

export interface DailyStats {
  followups: number
  quotes: number
  stage_changes: number
  tasks_done: number
  ai_actions: number
}

export interface DailyFacts {
  stats: DailyStats
  actions: string[]
  followups: string[]
  tasks_done: string[]
  tomorrow: string[]
}

export interface DailyReport {
  date: string
  status: ReportStatus
  content: string
  submitted_at?: string | null
  facts: DailyFacts
}

export interface DraftOut {
  source: "ai" | "template"
  content: string
}

export interface TeamMemberReport {
  user_id: string
  name: string
  status: ReportStatus
  content?: string | null
  submitted_at?: string | null
  stats: DailyStats
}

export interface TeamDaily {
  date: string
  submitted: number
  total: number
  members: TeamMemberReport[]
}

export interface SummaryOut {
  source: "ai" | "template"
  date_from: string
  date_to: string
  content: string
}

const keys = {
  daily: (d: string) => ["reports", "daily", d] as const,
  team: (d: string) => ["reports", "team", d] as const,
}

/** GET /api/reports/daily?date= */
export function useDailyReport(date: string, enabled = true) {
  return useQuery({
    queryKey: keys.daily(date),
    queryFn: ({ signal }) => api.get<DailyReport>("/api/reports/daily", { date }, signal),
    enabled,
    placeholderData: keepPreviousData,
  })
}

/** POST /api/reports/daily/draft：AI 按当天事实写草稿（不保存） */
export function useDraftReport() {
  return useMutation({
    mutationFn: (date: string) => api.post<DraftOut>("/api/reports/daily/draft", { date }),
    onError: notifyError,
  })
}

/** PUT /api/reports/daily：保存草稿或提交 */
export function useSaveReport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { date: string; content: string; submit: boolean }) =>
      api.put<DailyReport>("/api/reports/daily", body),
    onSuccess: (data, body) => {
      qc.setQueryData(keys.daily(body.date), data)
      void qc.invalidateQueries({ queryKey: ["reports", "team"] })
      toast.success(body.submit ? "日报已提交" : "草稿已保存")
    },
    onError: notifyError,
  })
}

/** GET /api/reports/team?date=（主管：本团队；管理员：全公司） */
export function useTeamReports(date: string, enabled = true) {
  return useQuery({
    queryKey: keys.team(date),
    queryFn: ({ signal }) => api.get<TeamDaily>("/api/reports/team", { date }, signal),
    enabled,
    placeholderData: keepPreviousData,
  })
}

/** POST /api/reports/team/summary：近 N 天团队汇总 */
export function useTeamSummary() {
  return useMutation({
    mutationFn: (days: number) => api.post<SummaryOut>("/api/reports/team/summary", { days }),
    onError: notifyError,
  })
}
