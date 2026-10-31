"use client"

import { AlarmClock, Play } from "lucide-react"
import { useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { RoleGate } from "@/components/shell/RoleGate"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { useJobRuns, useJobs, useRunJob, useUpdateJob, type JobItem, type JobRun } from "@/hooks/useJobs"
import { formatRelative } from "@/lib/format"

/** 会改业务数据的任务：开启和手动运行都要确认 */
const CHANGES_DATA = new Set(["pool_recycle"])
const OPTION_LABEL: Record<string, { before: string; after: string }> = {
  days: { before: "超过", after: "天没有跟进" },
}

function RunStatus({ run }: { run: JobRun }) {
  if (run.status === "running") return <Tag color="blue">运行中</Tag>
  return run.status === "ok" ? <Tag color="green">成功</Tag> : <Tag color="red">失败</Tag>
}

function trigger(run: JobRun): string {
  return run.trigger === "auto" ? "自动" : `手动 · ${run.triggered_by ?? ""}`
}

function OptionField({ job }: { job: JobItem }) {
  const update = useUpdateJob()
  const [values, setValues] = useState(() => Object.fromEntries(job.options.map((o) => [o.key, String(o.value)])))
  if (job.options.length === 0) return null
  const changed = job.options.some((o) => values[o.key] !== String(o.value))
  const invalid = Object.values(values).some((v) => !/^\d+$/.test(v) || Number(v) < 1 || Number(v) > 3650)
  return (
    <div className="flex flex-wrap items-center gap-2">
      {job.options.map((o) => (
        <label key={o.key} className="flex items-center gap-1.5 text-sm text-zinc-600">
          {OPTION_LABEL[o.key]?.before ?? o.key}
          <Input
            type="number"
            min={1}
            max={3650}
            value={values[o.key]}
            aria-label={`${job.title}：${OPTION_LABEL[o.key]?.before ?? ""}多少${OPTION_LABEL[o.key]?.after ?? ""}`}
            aria-invalid={invalid}
            className="h-7 w-20"
            onChange={(e) => setValues({ ...values, [o.key]: e.target.value })}
          />
          {OPTION_LABEL[o.key]?.after}
        </label>
      ))}
      {changed ? (
        <Button
          size="xs"
          variant="outline"
          disabled={invalid || update.isPending}
          onClick={() =>
            update.mutate({
              name: job.name,
              body: { options: Object.fromEntries(Object.entries(values).map(([k, v]) => [k, Number(v)])) },
            })
          }
        >
          保存
        </Button>
      ) : null}
      {invalid ? <span className="text-xs text-red-600">填 1～3650 之间的整数</span> : null}
    </div>
  )
}

function JobCard({ job, ask }: { job: JobItem; ask: ReturnType<typeof useConfirmAction>["ask"] }) {
  const update = useUpdateJob()
  const run = useRunJob()
  const [time, setTime] = useState(job.run_at)
  const risky = CHANGES_DATA.has(job.name)

  const toggle = (enabled: boolean) => {
    const go = () => update.mutate({ name: job.name, body: { enabled } })
    if (enabled && risky) {
      ask({
        title: `开启「${job.title}」？`,
        description: `${job.description}每天 ${job.run_at} 自动运行，客户负责人会被清空，原负责人会收到通知。`,
        confirmLabel: "确认开启",
        destructive: true,
        onConfirm: go,
      })
    } else go()
  }
  const runNow = () => {
    const go = () => run.mutate(job.name)
    if (risky) {
      ask({
        title: `立即运行「${job.title}」？`,
        description: "符合条件的客户会马上退回公海，不能自动撤销（可以由主管重新分配）。",
        confirmLabel: "立即运行",
        destructive: true,
        onConfirm: go,
      })
    } else go()
  }
  const saveTime = () => {
    if (/^\d{2}:\d{2}$/.test(time) && time !== job.run_at) update.mutate({ name: job.name, body: { run_at: time } })
  }

  return (
    <li className="space-y-3 rounded-lg border border-zinc-200 bg-white p-4" aria-label={job.title}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-medium text-zinc-900">{job.title}</h2>
            {job.weekdays_only ? <Tag>仅工作日</Tag> : null}
            {risky ? <Tag color="orange">会修改数据</Tag> : null}
          </div>
          <p className="text-sm text-zinc-500">{job.description}</p>
        </div>
        <Switch
          checked={job.enabled}
          onCheckedChange={toggle}
          disabled={update.isPending}
          aria-label={`${job.enabled ? "关闭" : "开启"}${job.title}`}
        />
      </div>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <label className="flex items-center gap-1.5 text-sm text-zinc-600">
          每天
          <Input
            type="time"
            step={60}
            value={time}
            aria-label={`${job.title}运行时间`}
            className="h-7 w-28"
            onChange={(e) => setTime(e.target.value)}
            onBlur={saveTime}
            onKeyDown={(e) => e.key === "Enter" && saveTime()}
          />
          运行（北京时间）
        </label>
        <OptionField job={job} />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-100 pt-3 text-sm">
        <div className="flex min-w-0 flex-wrap items-center gap-2 text-zinc-500">
          {job.last_run ? (
            <>
              <span>最近运行</span>
              <RunStatus run={job.last_run} />
              <span>
                {formatRelative(job.last_run.started_at)} · {trigger(job.last_run)}
              </span>
              {job.last_run.summary ? <span className="text-zinc-700">{job.last_run.summary}</span> : null}
            </>
          ) : (
            <span>还没有运行过</span>
          )}
        </div>
        <Button size="xs" variant="outline" disabled={run.isPending} onClick={runNow}>
          <Play />
          {run.isPending ? "运行中…" : "立即运行"}
        </Button>
      </div>
    </li>
  )
}

function RunHistory({ titles }: { titles: Record<string, string> }) {
  const runs = useJobRuns()
  if (!runs.data?.length) return null
  return (
    <section aria-label="运行记录" className="space-y-2">
      <h2 className="text-sm font-medium text-zinc-700">最近运行记录</h2>
      <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-zinc-200 text-xs text-zinc-500">
            <tr>
              <th className="px-4 py-2 font-normal">时间</th>
              <th className="py-2 font-normal">任务</th>
              <th className="py-2 font-normal">方式</th>
              <th className="py-2 font-normal">结果</th>
              <th className="px-4 py-2 font-normal">说明</th>
            </tr>
          </thead>
          <tbody>
            {runs.data.map((r) => (
              <tr key={r.id} className="border-b border-zinc-100 last:border-0">
                <td className="px-4 py-2 whitespace-nowrap text-zinc-500">{formatRelative(r.started_at)}</td>
                <td className="py-2">{titles[r.job] ?? r.job}</td>
                <td className="py-2 text-zinc-500">{trigger(r)}</td>
                <td className="py-2">
                  <RunStatus run={r} />
                </td>
                <td className="px-4 py-2 text-zinc-600">{r.summary}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function JobsBody() {
  const jobs = useJobs()
  const { ask, dialog } = useConfirmAction()
  if (jobs.isError) {
    return (
      <QueryError
        error={jobs.error}
        onRetry={() => void jobs.refetch()}
        retrying={jobs.isFetching}
        feature="定时任务"
      />
    )
  }
  if (!jobs.data) return <Skeleton className="h-64 w-full" />
  const titles = Object.fromEntries(jobs.data.map((j) => [j.name, j.title]))
  return (
    <div className="space-y-6">
      <p className="text-sm text-zinc-500">
        服务端每 30 秒检查一次，到点自动运行，每个任务一天只跑一次；服务在运行时间没启动时，当天启动后补跑。
        提醒都有去重，「立即运行」不会重复提醒。
      </p>
      <ul className="space-y-3">
        {jobs.data.map((j) => (
          <JobCard key={`${j.name}-${j.run_at}-${j.options.map((o) => o.value).join()}`} job={j} ask={ask} />
        ))}
      </ul>
      <RunHistory titles={titles} />
      {dialog}
    </div>
  )
}

/** 定时任务（仅管理员）：到期提醒、回款逾期、商机停滞、日报催交、公海自动回收 */
export default function JobsPage() {
  return (
    <PageFrame title="定时任务" icon={AlarmClock}>
      <RoleGate roles={["admin"]} config lockedText="定时任务由系统管理员配置">
        {/* 面板内留边距；内容多时在面板内滚动（PageFrame 面板本身不滚动） */}
        <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
          <JobsBody />
        </div>
      </RoleGate>
    </PageFrame>
  )
}
