"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"

/** 一次运行（自动 / 手动） */
export interface JobRun {
  id: string
  job: string
  trigger: "auto" | "manual"
  /** 手动运行的人 */
  triggered_by: string | null
  status: "running" | "ok" | "failed"
  summary: string | null
  started_at: string
  finished_at: string | null
}

/** GET /api/admin/jobs（仅管理员） */
export interface JobItem {
  name: string
  title: string
  description: string
  enabled: boolean
  /** HH:MM，北京时间 */
  run_at: string
  /** 只在工作日（周一到周五）运行 */
  weekdays_only: boolean
  options: { key: string; value: number }[]
  last_run: JobRun | null
}

export interface JobUpdate {
  enabled?: boolean
  run_at?: string
  options?: Record<string, number>
}

const KEYS = { jobs: ["admin", "jobs"] as const, runs: ["admin", "jobs", "runs"] as const }

export function useJobs() {
  return useQuery({
    queryKey: KEYS.jobs,
    queryFn: ({ signal }) => api.get<JobItem[]>("/api/admin/jobs", undefined, signal),
    // 自动运行由服务端调度，页面开着时定期刷新「最近运行」
    refetchInterval: 60_000,
  })
}

/** GET /api/admin/jobs/runs：最近的运行记录（全部任务） */
export function useJobRuns() {
  return useQuery({
    queryKey: KEYS.runs,
    queryFn: ({ signal }) => api.get<JobRun[]>("/api/admin/jobs/runs", { limit: 20 }, signal),
    refetchInterval: 60_000,
  })
}

function useRefresh() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: KEYS.jobs })
}

/** PATCH /api/admin/jobs/{name} */
export function useUpdateJob() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ name, body }: { name: string; body: JobUpdate }) =>
      api.patch<JobItem>(`/api/admin/jobs/${name}`, body),
    onSuccess: (job) => toast.success(`已保存「${job.title}」`),
    onError: notifyError,
    onSettled: refresh,
  })
}

/** POST /api/admin/jobs/{name}/run：立即运行一次，返回运行结果 */
export function useRunJob() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (name: string) => api.post<JobRun>(`/api/admin/jobs/${name}/run`),
    onSuccess: (run) =>
      run.status === "ok"
        ? toast.success("已运行", { description: run.summary ?? undefined })
        : toast.error("运行失败", { description: run.summary ?? undefined }),
    onError: notifyError,
    onSettled: refresh,
  })
}
