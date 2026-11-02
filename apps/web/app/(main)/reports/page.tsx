"use client"

import { BellRing, ClipboardList, Loader2, Sparkles } from "lucide-react"
import { useEffect, useState } from "react"
import { localDate, STATUS, DateInput, Facts, MemberRow, SummaryCard } from "@/components/reports/ReportParts"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { LINE_TABS_LIST, LINE_TABS_TRIGGER } from "@/components/biz/RecordTabs"
import { Tag } from "@/components/biz/Tag"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import {
  useDailyReport,
  useDraftReport,
  useSaveReport,
  useTeamReports,
  useTeamSummary,
  type SummaryOut,
} from "@/hooks/useReports"
import { usePushFlags, useRemindReports } from "@/hooks/useWecom"
import { useUnsavedGuard } from "@/hooks/useUnsavedGuard"
import { restorable } from "@/lib/report-backup"
import { LEAVE_REPORT_CONFIRM, REDRAFT_REPORT_CONFIRM } from "@/lib/confirm-texts"
import { readStorage, writeStorage } from "@/lib/storage"

/** 没保存的日报存在浏览器里：切走、刷新、切到团队日报后回来还在 */
const backupKey = (userId: string, date: string) => `sp.report.${userId}.${date}`

function MyReport() {
  const { userId } = useSession()
  const [date, setDate] = useState(localDate())
  const q = useDailyReport(date)
  const draft = useDraftReport()
  const save = useSaveReport()
  // 正在编辑的文字：按日期分开，切换日期后回到服务端内容
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [source, setSource] = useState<"ai" | "template" | null>(null)
  const content = edits[date] ?? q.data?.content ?? ""
  const setContent = (v: string) => setEdits((e) => ({ ...e, [date]: v }))
  const dirty = edits[date] !== undefined && edits[date] !== (q.data?.content ?? "")
  const [restored, setRestored] = useState<string | null>(null)
  const leaveDialog = useUnsavedGuard(dirty, LEAVE_REPORT_CONFIRM)

  // 打开某天的日报：浏览器里有没保存的内容就恢复
  const saved = q.data?.content
  useEffect(() => {
    if (!userId || saved === undefined) return
    const raw = readStorage(backupKey(userId, date))
    if (raw === null) return
    const backup = restorable(raw, saved)
    if (backup === null) return writeStorage(backupKey(userId, date), null)
    setEdits((e) => (e[date] === undefined ? { ...e, [date]: backup } : e))
    setRestored(date)
  }, [userId, date, saved])
  // 边写边存；和已保存的一样就清掉
  useEffect(() => {
    if (!userId || saved === undefined) return
    const text = edits[date]
    if (text === undefined) return
    writeStorage(backupKey(userId, date), text === saved ? null : JSON.stringify({ text, base: saved }))
  }, [userId, date, saved, edits])

  const { ask, dialog } = useConfirmAction()
  const runDraft = () =>
    draft.mutate(date, {
      onSuccess: (r) => {
        setContent(r.content)
        setSource(r.source)
      },
    })
  const generate = () => (content.trim() ? ask({ ...REDRAFT_REPORT_CONFIRM, onConfirm: runDraft }) : runDraft())
  const submit = (asSubmit: boolean) =>
    save.mutate(
      { date, content: content.trim(), submit: asSubmit },
      {
        onSuccess: () => {
          if (userId) writeStorage(backupKey(userId, date), null)
          setRestored(null)
          setEdits((e) => {
            const next = { ...e }
            delete next[date]
            return next
          })
        },
      },
    )

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4 sm:p-5">
      {dialog}
      {leaveDialog}
      <div className="flex flex-wrap items-center gap-2">
        <DateInput
          value={date}
          onChange={(d) => {
            setDate(d)
            setSource(null)
          }}
        />
        {q.data ? <Tag color={STATUS[q.data.status].color}>{STATUS[q.data.status].label}</Tag> : null}
        {q.data?.submitted_at ? (
          <span className="text-xs text-zinc-400">
            提交于 {new Date(q.data.submitted_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
          </span>
        ) : null}
      </div>
      {q.isPending ? (
        <Skeleton className="h-60 w-full" />
      ) : q.isError ? (
        <QueryError error={q.error} onRetry={() => void q.refetch()} feature="日报" />
      ) : (
        <div className="grid gap-3 lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <Facts facts={q.data.facts} />
          <section aria-label="日报内容" className="flex min-h-0 flex-col gap-2">
            <div className="flex items-center gap-2">
              <h3 className="font-medium">日报</h3>
              {source === "ai" ? (
                <span className="text-xs text-violet-600">AI 根据左侧记录生成，请核对后提交</span>
              ) : source === "template" ? (
                <span className="text-xs text-zinc-400">按模板生成（未连接大模型），请补充后提交</span>
              ) : null}
              <Button size="xs" variant="outline" className="ml-auto" disabled={draft.isPending} onClick={generate}>
                {draft.isPending ? <Loader2 className="animate-spin" /> : <Sparkles className="text-ai" />}
                AI 生成草稿
              </Button>
            </div>
            <Textarea
              rows={14}
              maxLength={5000}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="点「AI 生成草稿」根据今天的跟进、报价、任务自动写一版，改完再提交。"
              aria-label="日报正文"
              className="min-h-72 flex-1 resize-none"
            />
            <div className="flex items-center justify-end gap-2">
              {dirty ? (
                <span className="mr-auto text-xs text-amber-600">
                  {restored === date ? "已恢复上次没保存的内容，记得保存" : "有未保存的修改"}
                </span>
              ) : null}
              <Button
                variant="outline"
                size="sm"
                disabled={!content.trim() || save.isPending}
                onClick={() => submit(false)}
              >
                保存草稿
              </Button>
              <Button size="sm" disabled={!content.trim() || save.isPending} onClick={() => submit(true)}>
                {q.data.status === "submitted" ? "更新并提交" : "提交"}
              </Button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

function TeamReports() {
  const [date, setDate] = useState(localDate())
  const q = useTeamReports(date)
  const summary = useTeamSummary()
  const [result, setResult] = useState<SummaryOut | null>(null)
  const flags = usePushFlags()
  const remind = useRemindReports()
  const canRemind = flags.data?.report_remind === true && q.data && q.data.submitted < q.data.total
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <DateInput value={date} onChange={setDate} />
        {q.data ? (
          <span className="text-sm text-zinc-600">
            已提交 <span className="font-medium tabular-nums">{q.data.submitted}</span> / {q.data.total}
          </span>
        ) : null}
        {canRemind ? (
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto"
            disabled={remind.isPending}
            onClick={() => remind.mutate(date)}
          >
            <BellRing />
            群里提醒未提交
          </Button>
        ) : null}
        <Button
          size="sm"
          variant="outline"
          className={canRemind ? undefined : "ml-auto"}
          disabled={summary.isPending}
          onClick={() => summary.mutate(7, { onSuccess: setResult })}
        >
          {summary.isPending ? <Loader2 className="animate-spin" /> : <Sparkles className="text-ai" />}
          生成近 7 天汇总
        </Button>
      </div>
      {result ? <SummaryCard s={result} onClose={() => setResult(null)} /> : null}
      {q.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : q.isError ? (
        <QueryError error={q.error} onRetry={() => void q.refetch()} feature="团队日报" />
      ) : (
        <ul aria-label="团队日报" className="rounded-lg border border-zinc-200">
          {q.data.members.map((m) => (
            <MemberRow key={m.user_id} m={m} />
          ))}
        </ul>
      )}
    </div>
  )
}

/** 日报：销售看自己（系统记录 + AI 草稿 + 提交）；主管多一个团队视图；管理员只看团队 */
export default function ReportsPage() {
  const { role } = useSession()
  const [tab, setTab] = useState("mine")
  return (
    <PageFrame title="日报" icon={ClipboardList}>
      {role === "sales" ? (
        <MyReport />
      ) : role === "admin" ? (
        <TeamReports />
      ) : (
        <Tabs value={tab} onValueChange={setTab} className="flex min-h-0 flex-1 flex-col gap-0">
          <TabsList variant="line" aria-label="日报视图" className={LINE_TABS_LIST}>
            <TabsTrigger value="mine" className={LINE_TABS_TRIGGER}>
              我的日报
            </TabsTrigger>
            <TabsTrigger value="team" className={LINE_TABS_TRIGGER}>
              团队日报
            </TabsTrigger>
          </TabsList>
          <TabsContent value="mine" className="flex min-h-0 flex-1 flex-col">
            <MyReport />
          </TabsContent>
          <TabsContent value="team" className="flex min-h-0 flex-1 flex-col">
            <TeamReports />
          </TabsContent>
        </Tabs>
      )}
    </PageFrame>
  )
}
