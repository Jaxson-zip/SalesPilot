"use client"

import { Bot, ChevronLeft, ChevronRight, ScrollText, Search } from "lucide-react"
import { useState } from "react"

import { EmptyState } from "@/components/biz/EmptyState"
import { SimpleSelect } from "@/components/biz/FormControls"
import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { RoleGate } from "@/components/shell/RoleGate"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useDebounced } from "@/hooks/useDebounced"
import { useAuditLogs, type AuditItem } from "@/hooks/useAuditLogs"
import { cn } from "@/lib/utils"

const PAGE_SIZE = 50

/** 操作类别 → action 前缀（服务端按前缀筛选）；默认不看登录（登录记录多，会把业务操作挤到后面） */
const NO_LOGIN = "business"
const CATEGORIES = [
  { value: NO_LOGIN, label: "业务操作（不含登录）" },
  { value: "all", label: "全部操作（含登录）" },
  { value: "contact.phone_view", label: "查看电话" },
  { value: "export.", label: "导出数据" },
  { value: "settings.", label: "修改业务规则" },
  { value: "pack.", label: "行业包与价格" },
  { value: "customer.", label: "客户" },
  { value: "contact.", label: "联系人" },
  { value: "opportunity.", label: "商机" },
  { value: "quote.", label: "报价" },
  { value: "approval.", label: "审批" },
  { value: "expense.", label: "报销" },
  { value: "auth.", label: "登录" },
] as const

const ROLE_LABEL: Record<string, string> = { sales: "销售", manager: "主管", admin: "管理员" }

function time(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function Row({ item }: { item: AuditItem }) {
  const sensitive = item.action === "contact.phone_view" || item.action.startsWith("export.")
  return (
    <li className="flex gap-3 border-b border-zinc-100 px-4 py-2.5 text-sm sm:px-5">
      <span className="w-28 shrink-0 pt-0.5 text-xs text-zinc-400 tabular-nums">{time(item.created_at)}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-medium">{item.user_name ?? "匿名"}</span>
          {item.role ? <span className="text-xs text-zinc-400">{ROLE_LABEL[item.role] ?? item.role}</span> : null}
          <span className={cn(sensitive && "text-amber-700")}>{item.label}</span>
          {item.target_name ? <span className="truncate text-zinc-600">「{item.target_name}」</span> : null}
          {item.source === "agent" ? (
            <span className="inline-flex items-center gap-0.5 rounded bg-violet-50 px-1.5 text-xs text-violet-700">
              <Bot className="size-3" />
              AI 执行
            </span>
          ) : null}
        </div>
        {item.detail ? (
          <div className={cn("mt-0.5 line-clamp-2 text-xs", item.ok ? "text-zinc-500" : "text-red-600")}>
            {item.detail}
          </div>
        ) : null}
      </div>
      <div className="shrink-0">
        {item.ok ? <Tag color="green">成功</Tag> : <Tag color="red">{item.status === 429 ? "超限" : "被拒"}</Tag>}
      </div>
    </li>
  )
}

function AuditContent() {
  const [text, setText] = useState("")
  const q = useDebounced(text.trim(), 300)
  const [category, setCategory] = useState<string>(NO_LOGIN)
  const [result, setResult] = useState<"all" | "ok" | "failed">("all")
  const [source, setSource] = useState<"all" | "web" | "agent">("all")
  const [page, setPage] = useState(1)
  const query = useAuditLogs({
    q,
    action: category === "all" || category === NO_LOGIN ? undefined : category,
    exclude: category === NO_LOGIN ? "auth." : undefined,
    result: result === "all" ? undefined : result,
    source: source === "all" ? undefined : source,
    page,
    page_size: PAGE_SIZE,
  })
  const reset =
    <T,>(set: (v: T) => void) =>
    (v: T) => {
      set(v)
      setPage(1)
    }
  const total = query.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-100 px-4 py-2.5 sm:px-5">
        <div className="relative w-full sm:w-56">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-zinc-400" />
          <Input
            value={text}
            onChange={(e) => reset(setText)(e.target.value)}
            placeholder="搜操作人、操作、说明"
            aria-label="搜索操作日志"
            className="h-8 pl-8"
          />
        </div>
        <SimpleSelect
          value={category}
          onChange={reset(setCategory)}
          size="sm"
          ariaLabel="操作类别"
          className="w-44"
          options={CATEGORIES.map((c) => ({ value: c.value, label: c.label }))}
        />
        <SimpleSelect
          value={result}
          onChange={reset(setResult)}
          size="sm"
          ariaLabel="结果"
          className="w-28"
          options={[
            { value: "all", label: "全部结果" },
            { value: "ok", label: "成功" },
            { value: "failed", label: "被拒 / 失败" },
          ]}
        />
        <SimpleSelect
          value={source}
          onChange={reset(setSource)}
          size="sm"
          ariaLabel="来源"
          className="w-28"
          options={[
            { value: "all", label: "全部来源" },
            { value: "web", label: "网页操作" },
            { value: "agent", label: "AI 执行" },
          ]}
        />
        <span className="ml-auto text-xs text-zinc-500">
          共 <b className="text-zinc-800 tabular-nums">{total}</b> 条 · 日志只增不改
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {query.isPending ? (
          <div className="space-y-2 p-5">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : query.isError && !query.data ? (
          <QueryError error={query.error} onRetry={() => void query.refetch()} feature="操作日志" />
        ) : query.data.items.length === 0 ? (
          <EmptyState icon={ScrollText} title="没有符合条件的操作记录" />
        ) : (
          <ul aria-label="操作日志">
            {query.data.items.map((item) => (
              <Row key={item.id} item={item} />
            ))}
          </ul>
        )}
      </div>
      {pages > 1 ? (
        <div className="flex items-center justify-end gap-2 border-t border-zinc-100 px-4 py-2 text-xs text-zinc-500">
          第 {page} / {pages} 页
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="上一页"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            <ChevronLeft />
          </Button>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="下一页"
            disabled={page >= pages}
            onClick={() => setPage((p) => p + 1)}
          >
            <ChevronRight />
          </Button>
        </div>
      ) : null}
    </div>
  )
}

/** 操作日志：谁在什么时候做了什么（网页和 AI 的写操作、查看电话、导出），管理员看全公司，主管看本团队 */
export default function AuditPage() {
  const { role } = useSession()
  return (
    <PageFrame title="操作日志" icon={ScrollText}>
      <RoleGate roles={["manager", "admin"]} lockedText="操作日志仅主管和管理员可以查看">
        {role === "manager" || role === "admin" ? <AuditContent /> : null}
      </RoleGate>
    </PageFrame>
  )
}
