"use client"

import { ArrowRight, Clock, Handshake, Mail, MessageCircle, Phone, Sparkles, type LucideIcon } from "lucide-react"
import { forwardRef, useState } from "react"

import { PasteNotesDialog } from "@/components/agent/PasteNotesDialog"
import { LetterAvatar } from "@/components/biz/Chip"
import { EmptyState } from "@/components/biz/EmptyState"
import { DatePicker, SimpleSelect } from "@/components/biz/FormControls"
import { QueryError } from "@/components/biz/QueryStatus"
import { VoiceButton } from "@/components/biz/VoiceButton"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useActivities } from "@/hooks/useDashboard"
import { useContacts, useCreateFollowup, useFollowups } from "@/hooks/useFollowups"
import { useOpportunities } from "@/hooks/useOpportunities"
import { followupOccurredAt, formatRelative, localDate } from "@/lib/format"
import { FOLLOWUP_TYPE_LABEL } from "@/lib/labels"
import { buildTimeline, type TimelineEntry } from "@/lib/timeline"
import { QuickChips } from "@/components/biz/QuickChips"
import { useTemplates } from "@/hooks/useTemplates"
import { defaultQuoteOpportunity } from "@/lib/quote-actions"
import { insertTemplate, isUnfilledTemplate } from "@/lib/templates"
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

const NONE = "none"

/**
 * 这次跟进联系的是谁、关于哪一单（2026-11-04 走查：时间线上看不出来）。
 * 客户只有一个进行中的商机时默认选上；销售改过就不再覆盖，保存后保留，方便连续记同一单。
 */
function useFollowupTargets(customerId: string) {
  const [contactId, setContactId] = useState(NONE)
  const [oppId, setOppId] = useState(NONE)
  const [autoFor, setAutoFor] = useState<string | null>(null)
  const contacts = useContacts(customerId).data ?? []
  const opps = useOpportunities({ view: "mine", customer_id: customerId, page_size: 50 })
  const oppItems = (opps.data?.items ?? []).filter((o) => o.customer.id === customerId)
  if (opps.data && !opps.isPlaceholderData && autoFor !== customerId) {
    setAutoFor(customerId)
    setOppId(defaultQuoteOpportunity(oppItems) ?? NONE)
  }
  return {
    contactId,
    setContactId,
    oppId,
    setOppId,
    contactOptions: [{ value: NONE, label: "不指定联系人" }, ...contacts.map((c) => ({ value: c.id, label: c.name }))],
    oppOptions: [{ value: NONE, label: "不关联商机" }, ...oppItems.map((o) => ({ value: o.id, label: o.name }))],
    body: {
      // 选中的联系人刚被删掉时不再带上，免得保存被拦
      contact_id: contacts.some((c) => c.id === contactId) ? contactId : undefined,
      opportunity_id: oppId === NONE ? undefined : oppId,
    },
  }
}

/** 写跟进：内容 + 类型 Select + 日期 DatePicker + 联系人 / 商机 + 保存 */
export const FollowupComposer = forwardRef<
  HTMLTextAreaElement,
  { customerId: string; customerName: string; canAi?: boolean }
>(function FollowupComposer({ customerId, customerName, canAi }, ref) {
  const [pasting, setPasting] = useState(false)
  const [content, setContent] = useState("")
  const [type, setType] = useState<FollowupType>("phone")
  const [date, setDate] = useState(() => localDate())
  const create = useCreateFollowup(customerId)
  const targets = useFollowupTargets(customerId)
  const templates = useTemplates().data?.followup ?? []
  const unfilled = isUnfilledTemplate(content)
  const save = () =>
    create.mutate(
      { type, content: content.trim(), occurred_at: followupOccurredAt(date), ...targets.body },
      { onSuccess: () => setContent("") },
    )
  return (
    <div className="mb-5 rounded-lg border border-zinc-200 focus-within:border-zinc-300">
      <QuickChips
        label="跟进模板"
        className="px-3 pt-3"
        items={templates.map((t) => ({ key: t.id, label: t.label }))}
        onPick={(key) => {
          const tpl = templates.find((t) => t.id === key)
          if (!tpl) return
          setContent((c) => insertTemplate(c, tpl.content))
          setType(tpl.type)
        }}
      />
      <textarea
        ref={ref}
        rows={content.includes("\n") ? 5 : 2}
        value={content}
        maxLength={2000}
        onChange={(e) => setContent(e.target.value)}
        placeholder="记录一条跟进…（也可以直接让 AI 帮你记）"
        aria-label="跟进内容"
        className="block w-full resize-none bg-transparent px-3 pt-3 pb-1 outline-none placeholder:text-zinc-400"
      />
      {/* 底部工具行：与框边缘保持 12px，和上方输入区左右对齐 */}
      <div className="flex flex-wrap items-center gap-2 px-3 pt-1.5 pb-3">
        <div className="w-28">
          <SimpleSelect value={type} onChange={setType} options={TYPE_OPTIONS} size="sm" ariaLabel="跟进方式" />
        </div>
        <div className="w-36">
          <DatePicker value={date} onChange={setDate} size="sm" />
        </div>
        {/* 没有联系人 / 商机时不显示对应的选择框 */}
        {targets.contactOptions.length > 1 ? (
          <div className="w-32">
            <SimpleSelect
              value={targets.contactId}
              onChange={targets.setContactId}
              options={targets.contactOptions}
              size="sm"
              ariaLabel="联系人"
            />
          </div>
        ) : null}
        {targets.oppOptions.length > 1 ? (
          <div className="w-44">
            <SimpleSelect
              value={targets.oppId}
              onChange={targets.setOppId}
              options={targets.oppOptions}
              size="sm"
              ariaLabel="关联商机"
            />
          </div>
        ) : null}
        <VoiceButton value={content} onChange={(v) => setContent(v.slice(0, 2000))} />
        {canAi ? (
          <Button variant="ghost" size="sm" className="text-ai" onClick={() => setPasting(true)}>
            <Sparkles />
            粘贴纪要，AI 提炼
          </Button>
        ) : null}
        {/* ml-auto：窄屏换行后保存按钮仍靠右 */}
        {unfilled ? <span className="text-xs text-amber-700">模板还没填写内容</span> : null}
        <Button size="sm" className="ml-auto" disabled={!content.trim() || unfilled || create.isPending} onClick={save}>
          {create.isPending ? "保存中…" : "保存"}
        </Button>
      </div>
      {canAi ? <PasteNotesDialog open={pasting} onOpenChange={setPasting} customer={customerName} /> : null}
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
          // 保留换行：多行跟进原来挤成一行
          <div className="mt-1.5 rounded-lg border border-zinc-200 px-3 py-2.5 break-words whitespace-pre-wrap text-zinc-700">
            {e.content}
          </div>
        ) : null}
      </div>
    </div>
  )
}

/** Timeline：跟进记录 + 动态合并，按时间倒序 */
export function CustomerTimeline({
  customerId,
  role,
  owner,
  canWrite = true,
}: {
  customerId: string
  role: Role
  owner: string
  /** 能否写跟进（决定空状态的引导文字） */
  canWrite?: boolean
}) {
  const followups = useFollowups(customerId)
  const activities = useActivities({
    view: defaultScope(role),
    subject_type: "customer",
    subject_id: customerId,
    limit: 50,
    related: true,
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
    return (
      <EmptyState icon={Clock} title="还没有跟进记录" description={canWrite ? "在上方写下第一条跟进。" : undefined} />
    )
  return (
    <div className="relative">
      {entries.map((e, i) => (
        <Entry key={e.key} e={e} last={i === entries.length - 1} />
      ))}
    </div>
  )
}
