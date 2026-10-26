"use client"

import { ArrowRight, Clock, Handshake, Mail, MessageCircle, Phone, Sparkles, type LucideIcon } from "lucide-react"
import { forwardRef, useState } from "react"

import { LetterAvatar } from "@/components/biz/Chip"
import { EmptyState } from "@/components/biz/EmptyState"
import { DatePicker, SimpleSelect } from "@/components/biz/FormControls"
import { QueryError } from "@/components/biz/QueryStatus"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useActivities } from "@/hooks/useDashboard"
import { useCreateFollowup, useFollowups } from "@/hooks/useFollowups"
import { formatRelative, localDate } from "@/lib/format"
import { FOLLOWUP_TYPE_LABEL } from "@/lib/labels"
import { buildTimeline, type TimelineEntry } from "@/lib/timeline"
import { cn } from "@/lib/utils"
import { defaultScope } from "@/lib/views"
import type { FollowupType, Role } from "@/types/api"

const ICONS: Record<TimelineEntry["icon"], LucideIcon> = {
  phone: Phone,
  visit: Handshake,
  wechat: MessageCircle,
  email: Mail,
  ai: Sparkles,
  stage: ArrowRight,
  activity: Clock,
}

const TYPE_OPTIONS: { value: FollowupType; label: string }[] = (["phone", "visit", "wechat", "email"] as const).map(
  (t) => ({ value: t, label: FOLLOWUP_TYPE_LABEL[t] }),
)

/** 写跟进：内容 + 类型 Select + 日期 DatePicker + 保存 */
export const FollowupComposer = forwardRef<HTMLTextAreaElement, { customerId: string }>(function FollowupComposer(
  { customerId },
  ref,
) {
  const [content, setContent] = useState("")
  const [type, setType] = useState<FollowupType>("phone")
  const [date, setDate] = useState(() => localDate())
  const create = useCreateFollowup(customerId)
  const save = () =>
    create.mutate(
      { type, content: content.trim(), occurred_at: date ? `${date}T00:00:00` : undefined },
      { onSuccess: () => setContent("") },
    )
  return (
    <div className="mb-5 rounded-lg border border-zinc-200">
      <textarea
        ref={ref}
        rows={2}
        value={content}
        maxLength={2000}
        onChange={(e) => setContent(e.target.value)}
        placeholder="记录一条跟进…（也可以直接让 AI 帮你记）"
        className="w-full resize-none bg-transparent px-3 pt-2.5 outline-none placeholder:text-zinc-400"
      />
      <div className="flex flex-wrap items-center gap-2 px-2.5 pb-2.5">
        <div className="w-28">
          <SimpleSelect value={type} onChange={setType} options={TYPE_OPTIONS} size="sm" ariaLabel="跟进方式" />
        </div>
        <div className="w-36">
          <DatePicker value={date} onChange={setDate} size="sm" />
        </div>
        <div className="flex-1" />
        <Button size="sm" disabled={!content.trim() || create.isPending} onClick={save}>
          {create.isPending ? "保存中…" : "保存"}
        </Button>
      </div>
    </div>
  )
})

function Entry({ e, last }: { e: TimelineEntry; last: boolean }) {
  const Icon = ICONS[e.icon]
  return (
    <div className="relative flex gap-3 pb-5">
      {!last ? <span className="absolute top-7 bottom-0 left-3 w-px bg-zinc-200" /> : null}
      <span
        className={cn(
          "inline-flex size-6 shrink-0 items-center justify-center rounded-full border border-zinc-200 bg-white",
          e.actor === "AI" ? "text-ai" : "text-zinc-500",
        )}
      >
        <Icon className="size-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex h-6 min-w-0 items-center gap-1.5">
          <LetterAvatar name={e.actor} />
          <span className="shrink-0 font-medium">{e.actor === "AI" ? "AI 助手" : e.actor}</span>
          <span className="min-w-0 truncate text-zinc-500">{e.action}</span>
          <span className="flex-1" />
          <span className="shrink-0 text-xs text-zinc-400">{formatRelative(e.at)}</span>
        </div>
        {e.content ? (
          <div className="mt-1.5 rounded-lg border border-zinc-200 px-3 py-2.5 break-words text-zinc-700">
            {e.content}
          </div>
        ) : null}
      </div>
    </div>
  )
}

/** Timeline：跟进记录 + 动态合并，按时间倒序 */
export function CustomerTimeline({ customerId, role, owner }: { customerId: string; role: Role; owner: string }) {
  const followups = useFollowups(customerId)
  const activities = useActivities({
    view: defaultScope(role),
    subject_type: "customer",
    subject_id: customerId,
    limit: 50,
  })
  if (followups.isPending || activities.isPending)
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    )
  // 两个接口都失败才显示错误；只失败一个时显示另一个的数据
  if (followups.isError && activities.isError)
    return (
      <QueryError
        error={followups.error}
        onRetry={() => {
          void followups.refetch()
          void activities.refetch()
        }}
        feature="跟进记录"
      />
    )
  const entries = buildTimeline(followups.data ?? [], activities.data ?? [], owner)
  if (entries.length === 0)
    return <EmptyState icon={Clock} title="还没有跟进记录" description="在上方写下第一条跟进。" />
  return (
    <div className="relative">
      {entries.map((e, i) => (
        <Entry key={e.key} e={e} last={i === entries.length - 1} />
      ))}
    </div>
  )
}
