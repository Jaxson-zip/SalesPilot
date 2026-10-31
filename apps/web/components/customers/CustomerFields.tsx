"use client"

import { Hash, Link as LinkIcon, MapPin, Star, Tag as TagIcon, User, Users, Wallet } from "lucide-react"
import Link from "next/link"

import { Chip, LinkChip } from "@/components/biz/Chip"
import { FieldRow } from "@/components/biz/FieldRow"
import { InlineEditRow } from "@/components/biz/InlineEditRow"
import { colorFor, Tag } from "@/components/biz/Tag"
import { SubjectTasks } from "@/components/tasks/TaskList"
import { Skeleton } from "@/components/ui/skeleton"
import { useOpportunities } from "@/hooks/useOpportunities"
import { useUpdateCustomer } from "@/hooks/useCustomers"
import { INDUSTRY_OPTIONS, SIZE_OPTIONS } from "@/lib/customer"
import { displayHost, formatFen } from "@/lib/format"
import { STAGE_META } from "@/lib/labels"
import { defaultScope } from "@/lib/views"
import type { CustomerDetail, CustomerUpdate, Role } from "@/types/api"

function levelColor(level: string) {
  const head = level.trim().charAt(0).toUpperCase()
  return head === "A" ? "red" : head === "B" ? "blue" : "gray"
}

/** 客户的商机（客户详情「商机」标签页） */
export function CustomerOpportunities({ customerId, role }: { customerId: string; role: Role }) {
  const q = useOpportunities({ view: defaultScope(role), customer_id: customerId, page_size: 20 })
  if (q.isPending) return <Skeleton className="h-16 w-full" />
  if (q.isError) return <div className="text-zinc-400">商机加载失败</div>
  const items = q.data.items.filter((o) => o.customer.id === customerId)
  if (items.length === 0) return <div className="text-zinc-400">还没有商机</div>
  return (
    <div className="space-y-2">
      {items.map((o) => (
        <Link
          key={o.id}
          href={`/pipeline?opp=${encodeURIComponent(o.id)}`}
          className="block rounded-lg border border-zinc-200 p-3 hover:bg-zinc-50"
        >
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

/** RecordFields：客户字段 + 下一步（联系人、商机在右侧标签页） */
const LEVELS = [
  { value: "A", label: "A 级（重点客户）" },
  { value: "B", label: "B 级" },
  { value: "C", label: "C 级" },
]
const toOptions = (xs: readonly string[]) => xs.map((x) => ({ value: x, label: x }))

export function CustomerFields({
  c,
  editable,
  focusTaskId,
}: {
  c: CustomerDetail
  editable: boolean
  /** 从通知 / 待办点进来时要定位的任务 */
  focusTaskId?: string | null
}) {
  const update = useUpdateCustomer(c.id)
  const save = (key: keyof CustomerUpdate) => (v: string | number | null) => update.mutateAsync({ [key]: v })
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
      <InlineEditRow
        icon={TagIcon}
        label="行业"
        kind="select"
        options={toOptions(INDUSTRY_OPTIONS)}
        value={c.industry}
        editable={editable}
        display={c.industry ? <Tag color={colorFor(c.industry)}>{c.industry}</Tag> : "—"}
        onSave={save("industry")}
      />
      <InlineEditRow
        icon={Star}
        label="等级"
        kind="select"
        required
        options={LEVELS}
        value={c.level}
        editable={editable}
        display={c.level ? <Tag color={levelColor(c.level)}>{c.level}</Tag> : "—"}
        onSave={save("level")}
      />
      <InlineEditRow
        icon={Users}
        label="规模"
        kind="select"
        options={toOptions(SIZE_OPTIONS)}
        value={c.size}
        editable={editable}
        display={c.size ?? "—"}
        onSave={save("size")}
      />
      <InlineEditRow
        icon={MapPin}
        label="地址"
        kind="text"
        value={c.address}
        editable={editable}
        display={c.address ?? "—"}
        placeholder="例如：深圳市南山区科技园"
        onSave={save("address")}
      />
      <InlineEditRow
        icon={LinkIcon}
        label="网站"
        kind="text"
        value={c.website}
        editable={editable}
        display={c.website ? <LinkChip>{displayHost(c.website)}</LinkChip> : "—"}
        placeholder="https://"
        onSave={save("website")}
      />
      <FieldRow icon={User} label="负责人">
        {c.owner ? <Chip name={c.owner.name} /> : "—"}
      </FieldRow>
      <InlineEditRow
        icon={Wallet}
        label="年度预算"
        kind="money"
        value={c.annual_budget}
        editable={editable}
        display={<span className="tabular-nums">{c.annual_budget === null ? "—" : formatFen(c.annual_budget)}</span>}
        onSave={save("annual_budget")}
      />
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
      <div className="mt-5">
        <SubjectTasks
          subjectType="customer"
          subjectId={c.id}
          subjectName={c.name}
          editable={editable}
          focusId={focusTaskId}
        />
      </div>
    </>
  )
}
