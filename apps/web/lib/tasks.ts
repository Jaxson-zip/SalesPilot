/** 任务与下一步（契约 v3 §12）的纯函数：到期快捷选项、到期文案、商机卡片上的「下一步」 */
import { addDays, beijingInstant, daysBetween, localClock, localDate } from "@/lib/format"
import { isFinalStage } from "@/lib/pipeline"
import type { OpportunityItem, TaskType } from "@/types/api"

export const TASK_TYPE_LABEL: Record<TaskType, string> = {
  call: "电话",
  visit: "拜访",
  email: "邮件",
  meeting: "会议",
  todo: "待办",
}

export const TASK_TYPE_OPTIONS: { value: TaskType; label: string }[] = (
  ["call", "visit", "meeting", "email", "todo"] as const
).map((t) => ({ value: t, label: TASK_TYPE_LABEL[t] }))

export type DueShortcut = "today" | "tomorrow" | "next_monday"

export const DUE_SHORTCUTS: { value: DueShortcut; label: string }[] = [
  { value: "today", label: "今天" },
  { value: "tomorrow", label: "明天" },
  { value: "next_monday", label: "下周一" },
]

/** 新建任务默认的到期时间 */
export const DEFAULT_DUE_TIME = "10:00"

const WEEKDAY = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
const pad = (n: number) => String(n).padStart(2, "0")

/** 快捷选项 → 业务日期 YYYY-MM-DD（北京时间）；「下周一」= 下一个周一（今天是周一时为 7 天后） */
export function dueShortcutDate(kind: DueShortcut, now: Date = new Date()): string {
  const today = localDate(now)
  if (kind === "today") return today
  if (kind === "tomorrow") return addDays(today, 1)
  const delta = (8 - weekday(today)) % 7 || 7
  return addDays(today, delta)
}

/** 业务日期 + 北京时间（HH:mm）→ ISO 8601（UTC）；格式不对返回 null */
export function toDueIso(date: string, time: string): string | null {
  const dm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date)
  const tm = /^(\d{1,2}):(\d{2})$/.exec(time || DEFAULT_DUE_TIME)
  if (!dm || !tm) return null
  const h = Number(tm[1])
  const mi = Number(tm[2])
  if (h > 23 || mi > 59) return null
  return beijingInstant(date, `${pad(h)}:${pad(mi)}`)?.toISOString() ?? null
}

function weekday(date: string): number {
  return new Date(`${date}T00:00:00Z`).getUTCDay()
}

/** 到期日的相对说法（按北京时间的日期）：今天 / 明天 / 昨天 / 周X（7 天内）/ MM-DD */
export function dueDayLabel(iso: string, now: Date = new Date()): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "—"
  const day = localDate(d)
  const today = localDate(now)
  const diff = daysBetween(today, day)
  if (diff === 0) return "今天"
  if (diff === 1) return "明天"
  if (diff === -1) return "昨天"
  if (diff > 1 && diff < 7) return WEEKDAY[weekday(day)]
  return day.slice(0, 4) === today.slice(0, 4) ? day.slice(5) : day
}

/** 任务列表里的到期文案：「明天 10:00」；逾期：「已逾期 · 10-24」 */
export function dueText(iso: string, overdue: boolean, now: Date = new Date()): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "—"
  const day = dueDayLabel(iso, now)
  if (overdue) return `已逾期 · ${day}`
  return `${day} ${localClock(d)}`
}

/** 逾期：以后端的 overdue 为准；后端没给时按当前时间判断 */
export function isTaskOverdue(
  t: { due_at: string; done?: boolean; overdue?: boolean },
  now: Date = new Date(),
): boolean {
  if (t.done) return false
  if (typeof t.overdue === "boolean") return t.overdue
  const due = Date.parse(t.due_at)
  return !Number.isNaN(due) && due < now.getTime()
}

export type NextStepView =
  | { kind: "task"; text: string; overdue: boolean }
  /** 未终态且没有下一步：淡黄色「未安排下一步」提示（Pipedrive 做法） */
  | { kind: "missing" }
  /** 终态，或后端还没返回 next_task 字段：不显示 */
  | { kind: "hidden" }

export function nextStepView(opp: Pick<OpportunityItem, "stage" | "next_task">, now: Date = new Date()): NextStepView {
  if (isFinalStage(opp.stage) || opp.next_task === undefined) return { kind: "hidden" }
  if (opp.next_task === null) return { kind: "missing" }
  const t = opp.next_task
  return {
    kind: "task",
    text: `下一步：${t.title} · ${dueDayLabel(t.due_at, now)}`,
    overdue: isTaskOverdue(t, now),
  }
}

/** 停滞提醒（v3 §13）：stale 由后端按 rules.yaml 的 stale_days 判断，前端只负责文案 */
export function staleText(opp: Pick<OpportunityItem, "stale" | "idle_days">): string | null {
  if (!opp.stale) return null
  return typeof opp.idle_days === "number" ? `已 ${opp.idle_days} 天未跟进` : "长时间未跟进"
}

/** 完成任务后的提示文案 */
export function taskDoneText(title: string): string {
  return `已完成「${title}」`
}

/** 工作台待办：逾期在前、今天到期在后，各自按到期时间升序，按 id 去重（两次查询可能有重叠） */
export function mergeTodoTasks<T extends { id: string; due_at: string }>(overdue: T[], today: T[]): T[] {
  const seen = new Set<string>()
  const byDue = (a: T, b: T) => Date.parse(a.due_at) - Date.parse(b.due_at)
  const out: T[] = []
  for (const t of [...[...overdue].sort(byDue), ...[...today].sort(byDue)]) {
    if (seen.has(t.id)) continue
    seen.add(t.id)
    out.push(t)
  }
  return out
}

/** 任务标题跳转：商机 → 看板并打开商机侧栏；客户 → 客户详情 */
export function taskSubjectHref(t: { subject_type: string; subject_id: string }): string {
  const id = encodeURIComponent(t.subject_id)
  return t.subject_type === "opportunity" ? `/pipeline?opp=${id}` : `/customers/${id}`
}

/** 点任务：打开所属商机 / 客户，并定位到这条任务（与通知里的链接一致） */
export function taskHref(t: { id: string; subject_type: string; subject_id: string }): string {
  const base = taskSubjectHref(t)
  return `${base}${base.includes("?") ? "&" : "?"}task=${encodeURIComponent(t.id)}`
}

/** 工作台标题下的待办摘要；后端还没返回 tasks_today 时为空串 */
export function todoSummary(today: number | undefined, overdue: number | undefined): string {
  if (today === undefined) return ""
  return `今天 ${today} 项待办${overdue ? `，${overdue} 项已逾期` : ""}`
}
