"use client"

import { Hash, Link as LinkIcon, MapPin, Plus, Star, Tag as TagIcon, User, Users, Wallet } from "lucide-react"
import Link from "next/link"

import { Chip, LetterAvatar, LinkChip } from "@/components/biz/Chip"
import { FieldRow } from "@/components/biz/FieldRow"
import { colorFor, Tag } from "@/components/biz/Tag"
import { Skeleton } from "@/components/ui/skeleton"
import { useContacts } from "@/hooks/useFollowups"
import { useOpportunities } from "@/hooks/useOpportunities"
import { displayHost, formatFen } from "@/lib/format"
import { STAGE_META } from "@/lib/labels"
import { isNotImplemented } from "@/lib/errors"
import { defaultScope } from "@/lib/views"
import type { CustomerDetail, Role } from "@/types/api"

function levelColor(level: string) {
  const head = level.trim().charAt(0).toUpperCase()
  return head === "A" ? "red" : head === "B" ? "blue" : "gray"
}

function SectionTitle({ children }: { children: string }) {
  return <div className="mt-5 mb-1.5 text-zinc-500">{children}</div>
}

function Contacts({ customerId }: { customerId: string }) {
  const q = useContacts(customerId)
  if (q.isPending) return <Skeleton className="h-9 w-full" />
  if (q.isError)
    return <div className="text-zinc-400">{isNotImplemented(q.error) ? "联系人接口开发中" : "联系人加载失败"}</div>
  if (q.data.length === 0) return <div className="text-zinc-400">还没有联系人</div>
  return (
    <>
      {q.data.map((c) => (
        <div key={c.id} className="flex h-9 min-w-0 items-center gap-2 rounded px-1.5 hover:bg-zinc-100">
          <LetterAvatar name={c.name} className="size-6 text-[11px]" />
          <span className="shrink-0 font-medium">{c.name}</span>
          <span className="min-w-0 truncate text-zinc-500">
            {[c.title, c.is_decision_maker ? "决策人" : null].filter(Boolean).join(" · ")}
          </span>
        </div>
      ))}
    </>
  )
}

function Opportunities({ customerId, role }: { customerId: string; role: Role }) {
  const q = useOpportunities({ view: defaultScope(role), customer_id: customerId, page_size: 20 })
  if (q.isPending) return <Skeleton className="h-16 w-full" />
  if (q.isError)
    return <div className="text-zinc-400">{isNotImplemented(q.error) ? "商机接口开发中" : "商机加载失败"}</div>
  const items = q.data.items.filter((o) => o.customer.id === customerId)
  if (items.length === 0) return <div className="text-zinc-400">还没有商机</div>
  return (
    <div className="space-y-2">
      {items.map((o) => (
        <Link key={o.id} href="/pipeline" className="block rounded-lg border border-zinc-200 p-3 hover:bg-zinc-50">
          <div className="flex justify-between gap-2">
            <span className="truncate font-medium">{o.name}</span>
            <span className="shrink-0 tabular-nums">{formatFen(o.amount)}</span>
          </div>
          <div className="mt-1.5 flex items-center gap-1.5">
            <Tag color={STAGE_META[o.stage].color}>{STAGE_META[o.stage].label}</Tag>
            {o.expected_close_date ? (
              <span className="text-xs text-zinc-500">预计 {o.expected_close_date.slice(5, 10)} 成交</span>
            ) : null}
          </div>
        </Link>
      ))}
    </div>
  )
}

/** RecordFields：客户字段 + 联系人 + 关联商机 */
export function CustomerFields({ c, role }: { c: CustomerDetail; role: Role }) {
  return (
    <>
      <div className="mb-4 flex items-center gap-3">
        <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg border border-zinc-200 text-[15px] font-semibold">
          {c.name.slice(0, 1)}
        </span>
        <div className="min-w-0">
          <div className="truncate text-base font-semibold">{c.name}</div>
          <div className="text-xs text-zinc-400">创建于 {c.created_at.slice(0, 10)}</div>
        </div>
      </div>
      <FieldRow icon={TagIcon} label="行业">
        {c.industry ? <Tag color={colorFor(c.industry)}>{c.industry}</Tag> : "—"}
      </FieldRow>
      <FieldRow icon={Star} label="等级">
        {c.level ? <Tag color={levelColor(c.level)}>{c.level}</Tag> : "—"}
      </FieldRow>
      <FieldRow icon={Users} label="规模">
        {c.size ?? "—"}
      </FieldRow>
      <FieldRow icon={MapPin} label="地址">
        {c.address ?? "—"}
      </FieldRow>
      <FieldRow icon={LinkIcon} label="网站">
        {c.website ? <LinkChip>{displayHost(c.website)}</LinkChip> : "—"}
      </FieldRow>
      <FieldRow icon={User} label="负责人">
        {c.owner ? <Chip name={c.owner.name} /> : "—"}
      </FieldRow>
      <FieldRow icon={Wallet} label="年度预算">
        <span className="tabular-nums">{c.annual_budget === null ? "—" : formatFen(c.annual_budget)}</span>
      </FieldRow>
      <FieldRow icon={Hash} label="标签">
        {c.tags.length ? (
          <span className="inline-flex gap-1">
            {c.tags.map((t) => (
              <Tag key={t} color={colorFor(t)}>
                {t}
              </Tag>
            ))}
          </span>
        ) : (
          "—"
        )}
      </FieldRow>
      <div className="mt-5 mb-1.5 flex items-center justify-between text-zinc-500">
        <span>联系人</span>
        <Plus className="size-3.5 text-zinc-300" aria-hidden />
      </div>
      <Contacts customerId={c.id} />
      <SectionTitle>商机</SectionTitle>
      <Opportunities customerId={c.id} role={role} />
    </>
  )
}
