"use client"

import { BellRing, ChevronDown, ClipboardList, Copy, Loader2, Send, Sparkles } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { LINE_TABS_LIST, LINE_TABS_TRIGGER } from "@/components/biz/RecordTabs"
import { Tag } from "@/components/biz/Tag"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import {
  useDailyReport,
  useDraftReport,
  useSaveReport,
  useTeamReports,
  useTeamSummary,
  type DailyFacts,
  type DailyStats,
  type ReportStatus,
  type SummaryOut,
  type TeamMemberReport,
} from "@/hooks/useReports"
import { usePushFlags, usePushSummary, useRemindReports } from "@/hooks/useWecom"
import { cn } from "@/lib/utils"

/** 本地日期 yyyy-mm-dd（服务端按北京时间算「当天」） */
function localDate(offset = 0): string {
  const d = new Date(Date.now() + offset * 86_400_000)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const STATUS: Record<ReportStatus, { label: string; color: "gray" | "yellow" | "green" }> = {
  none: { label: "未填写", color: "gray" },
  draft: { label: "草稿", color: "yellow" },
  submitted: { label: "已提交", color: "green" },
}

function DateInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Input
      type="date"
      value={value}
      min={localDate(-31)}
      max={localDate()}
      aria-label="日报日期"
      className="h-8 w-40"
      onChange={(e) => e.target.value && onChange(e.target.value)}
    />
  )
}

function StatLine({ s }: { s: DailyStats }) {
  return (
    <span className="text-xs text-zinc-500 tabular-nums">
      跟进 {s.followups} · 报价 {s.quotes} · 阶段推进 {s.stage_changes} · 完成任务 {s.tasks_done}
      {s.ai_actions ? ` · AI 代办 ${s.ai_actions}` : ""}
    </span>
  )
}

const FOLD_AT = 8

function FactList({ title, items }: { title: string; items: string[] }) {
  const [all, setAll] = useState(false)
  if (!items.length) return null
  const shown = all ? items : items.slice(0, FOLD_AT)
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-zinc-500">{title}</div>
      <ul className="space-y-0.5 text-zinc-700">
        {shown.map((s, i) => (
          <li key={`${i}-${s}`} className="line-clamp-2">
            · {s}
          </li>
        ))}
      </ul>
      {items.length > FOLD_AT ? (
        <button type="button" className="mt-1 text-xs text-zinc-500 hover:text-zinc-800" onClick={() => setAll(!all)}>
          {all ? "收起" : `展开全部 ${items.length} 条`}
        </button>
      ) : null}
    </div>
  )
}

/** 当天系统记录（AI 写草稿只用这些事实） */
function Facts({ facts }: { facts: DailyFacts }) {
  const s = facts.stats
  const tiles = [
    { label: "跟进", value: s.followups },
    { label: "报价", value: s.quotes },
    { label: "阶段推进", value: s.stage_changes },
    { label: "完成任务", value: s.tasks_done },
  ]
  const empty = !facts.actions.length && !facts.followups.length && !facts.tomorrow.length
  return (
    <section aria-label="当天记录" className="space-y-3 rounded-lg border border-zinc-200 p-4 text-sm">
      <div className="grid grid-cols-4 gap-2">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-md bg-zinc-50 px-2 py-1.5 text-center">
            <div className="text-lg font-semibold tabular-nums">{t.value}</div>
            <div className="text-xs text-zinc-500">{t.label}</div>
          </div>
        ))}
      </div>
      {empty ? (
        <p className="text-zinc-400">这一天系统里还没有你的操作记录。</p>
      ) : (
        <>
          <FactList title="客户跟进" items={facts.followups} />
          <FactList title="系统操作" items={facts.actions} />
          <FactList title="明天到期的任务" items={facts.tomorrow} />
        </>
      )}
    </section>
  )
}

function MyReport() {
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

  const generate = () => {
    if (content.trim() && !window.confirm("用新生成的草稿覆盖当前内容？")) return
    draft.mutate(date, {
      onSuccess: (r) => {
        setContent(r.content)
        setSource(r.source)
      },
    })
  }
  const submit = (asSubmit: boolean) =>
    save.mutate(
      { date, content: content.trim(), submit: asSubmit },
      {
        onSuccess: () =>
          setEdits((e) => {
            const next = { ...e }
            delete next[date]
            return next
          }),
      },
    )

  return (
    <div className="mx-auto w-full max-w-5xl space-y-3 p-4 sm:p-5">
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
        <div className="grid items-start gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <Facts facts={q.data.facts} />
          <section aria-label="日报内容" className="space-y-2">
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
              className="min-h-72"
            />
            <div className="flex items-center justify-end gap-2">
              {dirty ? <span className="mr-auto text-xs text-amber-600">有未保存的修改</span> : null}
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

function MemberRow({ m }: { m: TeamMemberReport }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="border-b border-zinc-100 last:border-0">
      <button
        type="button"
        disabled={!m.content}
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label={`${m.name} 的日报`}
        className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm disabled:cursor-default"
      >
        <span className="w-16 shrink-0 font-medium">{m.name}</span>
        <Tag color={STATUS[m.status].color}>{STATUS[m.status].label}</Tag>
        <span className="min-w-0 flex-1 truncate">
          <StatLine s={m.stats} />
        </span>
        {m.content ? (
          <ChevronDown className={cn("size-4 shrink-0 text-zinc-400 transition-transform", !open && "-rotate-90")} />
        ) : null}
      </button>
      {open && m.content ? (
        <div className="px-4 pb-3 text-sm whitespace-pre-line text-zinc-700">{m.content}</div>
      ) : null}
    </li>
  )
}

function SummaryCard({ s, onClose }: { s: SummaryOut; onClose: () => void }) {
  const flags = usePushFlags()
  const push = usePushSummary()
  const canPush = flags.data?.report_summary === true
  return (
    <section
      aria-label="团队汇总"
      className="space-y-2 rounded-lg border border-violet-200 bg-violet-50/50 p-4 text-sm"
    >
      <div className="flex items-center gap-1.5 font-medium text-violet-800">
        <Sparkles className="size-4" />
        团队汇总（{s.date_from.slice(5)} 至 {s.date_to.slice(5)}）
        {s.source === "template" ? <span className="text-xs font-normal text-zinc-500">按统计生成</span> : null}
      </div>
      <div className="whitespace-pre-line text-zinc-800">{s.content}</div>
      <div className="flex justify-end gap-2">
        <Button size="xs" variant="ghost" onClick={onClose}>
          收起
        </Button>
        <Button
          size="xs"
          variant="outline"
          onClick={() =>
            void navigator.clipboard.writeText(s.content).then(
              () => toast.success("已复制"),
              () => toast.error("复制失败，请手动选择文字"),
            )
          }
        >
          <Copy />
          复制
        </Button>
        {canPush ? (
          <Button size="xs" variant="outline" disabled={push.isPending} onClick={() => push.mutate(s.content)}>
            <Send />
            推送到企业微信群
          </Button>
        ) : null}
      </div>
    </section>
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
    <div className="mx-auto w-full max-w-4xl space-y-3 p-4 sm:p-5">
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
          <TabsContent value="mine" className="min-h-0 flex-1 overflow-y-auto">
            <MyReport />
          </TabsContent>
          <TabsContent value="team" className="min-h-0 flex-1 overflow-y-auto">
            <TeamReports />
          </TabsContent>
        </Tabs>
      )}
    </PageFrame>
  )
}
