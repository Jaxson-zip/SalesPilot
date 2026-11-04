"use client"

import { ChevronDown, Copy, Send, Sparkles } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  type DailyFacts,
  type DailyStats,
  type ReportStatus,
  type SummaryOut,
  type TeamMemberReport,
} from "@/hooks/useReports"
import { usePushFlags, usePushSummary } from "@/hooks/useWecom"
import { copyText } from "@/lib/clipboard"
import { addDays, localDate as businessDate } from "@/lib/format"
import { cn } from "@/lib/utils"

/** 日报日期 yyyy-mm-dd：按北京时间（与服务端的「当天」一致），offset 为相对今天的天数 */
export function localDate(offset = 0): string {
  return addDays(businessDate(), offset)
}

export const STATUS: Record<ReportStatus, { label: string; color: "gray" | "yellow" | "green" }> = {
  none: { label: "未填写", color: "gray" },
  draft: { label: "草稿", color: "yellow" },
  submitted: { label: "已提交", color: "green" },
}

export function DateInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
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

/** 统计口径（与 core report_service._deal_counts 一致） */
export const STATS_NOTE =
  "新建报价：当天新建的报价单张数（含 AI 生成，提交、发送不重复计）；阶段推进：商机阶段变化次数，含报价发给客户后的自动推进。"

export function StatLine({ s }: { s: DailyStats }) {
  return (
    <span className="text-xs text-zinc-500 tabular-nums">
      跟进 {s.followups} · 新建报价 {s.quotes} · 阶段推进 {s.stage_changes} · 完成任务 {s.tasks_done}
      {s.ai_actions ? ` · AI 代办 ${s.ai_actions}` : ""}
    </span>
  )
}

export const FOLD_AT = 8

export function FactList({ title, items }: { title: string; items: string[] }) {
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
export function Facts({ facts }: { facts: DailyFacts }) {
  const s = facts.stats
  const tiles = [
    { label: "跟进", value: s.followups },
    { label: "新建报价", value: s.quotes },
    { label: "阶段推进", value: s.stage_changes },
    { label: "完成任务", value: s.tasks_done },
  ]
  const empty = !facts.actions.length && !facts.followups.length && !facts.tomorrow.length
  return (
    <section
      aria-label="当天记录"
      className="space-y-3 rounded-lg border border-zinc-200 p-4 text-sm lg:h-full lg:overflow-y-auto"
    >
      <div className="grid grid-cols-4 gap-2">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-md bg-zinc-50 px-2 py-1.5 text-center">
            <div className="text-lg font-semibold tabular-nums">{t.value}</div>
            <div className="text-xs text-zinc-500">{t.label}</div>
          </div>
        ))}
      </div>
      <p className="text-xs text-zinc-500">{STATS_NOTE}</p>
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

export function MemberRow({ m }: { m: TeamMemberReport }) {
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

export function SummaryCard({ s, onClose }: { s: SummaryOut; onClose: () => void }) {
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
            void copyText(s.content).then((ok) =>
              ok ? toast.success("已复制") : toast.error("复制失败，请手动选择文字"),
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
