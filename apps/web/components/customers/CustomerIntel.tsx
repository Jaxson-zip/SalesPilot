"use client"

import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, Lightbulb } from "lucide-react"

import { Alert } from "@/components/biz/Alert"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { formatFen } from "@/lib/format"
import { cn } from "@/lib/utils"

export interface CompanyIntel {
  customer_id: string
  provider: string
  demo: boolean
  notice?: string | null
  profile: {
    full_name: string
    credit_code: string
    legal_rep: string
    registered_capital: string
    founded: string
    status: string
    industry?: string | null
    staff_size: string
    address: string
  }
  news: { date: string; title: string; source: string; sentiment: "positive" | "neutral" | "negative" }[]
  tenders: {
    date: string
    title: string
    kind: "招标" | "中标" | "采购意向"
    amount?: number | null
    winner?: string | null
    opportunity: boolean
  }[]
  risks: { level: "low" | "medium" | "high"; text: string }[]
  signals: string[]
}

/** GET /api/customers/{id}/intel */
export function useCustomerIntel(id: string) {
  return useQuery({
    queryKey: ["customers", id, "intel"],
    queryFn: ({ signal }) => api.get<CompanyIntel>(`/api/customers/${id}/intel`, undefined, signal),
    staleTime: 10 * 60_000,
  })
}

const SENTIMENT = {
  positive: { label: "正面", color: "green" },
  neutral: { label: "中性", color: "gray" },
  negative: { label: "负面", color: "red" },
} as const

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="space-y-2">
      <h3 className="text-sm font-medium">{title}</h3>
      {children}
    </section>
  )
}

/** 客户详情「外部情报」：工商信息、给销售的提示、招投标、新闻舆情；演示数据顶部明确标注 */
export function CustomerIntel({ customerId }: { customerId: string }) {
  const q = useCustomerIntel(customerId)
  if (q.isPending) return <Skeleton className="h-60 w-full" />
  if (q.isError) return <QueryError error={q.error} onRetry={() => void q.refetch()} feature="外部情报" />
  const d = q.data
  const p = d.profile
  const rows: [string, string][] = [
    ["企业全称", p.full_name],
    ["统一社会信用代码", p.credit_code],
    ["法定代表人", p.legal_rep],
    ["注册资本", p.registered_capital],
    ["成立日期", p.founded],
    ["经营状态", p.status],
    ["人员规模", p.staff_size],
    ["注册地址", p.address],
  ]
  return (
    <div className="space-y-5 text-sm">
      {d.demo ? (
        <Alert tone="warn" title="演示数据">
          {d.notice ?? "不是真实信息"}。接入企查查、天眼查或招投标平台的开放接口后，这里会显示真实数据。
        </Alert>
      ) : null}

      {d.signals.length ? (
        <Section title="给你的提示">
          <ul className="space-y-1.5">
            {d.signals.map((s) => (
              <li key={s} className="flex gap-2 rounded-md bg-amber-50 px-3 py-2 text-amber-900">
                <Lightbulb className="mt-0.5 size-4 shrink-0" />
                {s}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <Section title="招投标">
        <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
          {d.tenders.map((t) => (
            <li key={`${t.date}-${t.title}`} className="flex flex-wrap items-start gap-x-2 gap-y-1 px-3 py-2.5">
              <span className="w-20 shrink-0 text-xs text-zinc-400 tabular-nums">{t.date}</span>
              <Tag color={t.kind === "中标" ? "gray" : "blue"}>{t.kind}</Tag>
              <span
                className={cn("min-w-0 flex-1 max-sm:order-last max-sm:basis-full", t.opportunity && "font-medium")}
              >
                {t.title}
                {t.winner ? <span className="block text-xs text-zinc-500">中标方：{t.winner}</span> : null}
              </span>
              {t.amount ? <span className="text-zinc-600 tabular-nums">{formatFen(t.amount)}</span> : null}
              {t.opportunity ? <Tag color="orange">与我们相关</Tag> : null}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="新闻舆情">
        <ul className="space-y-1.5">
          {d.news.map((n) => (
            <li key={`${n.date}-${n.title}`} className="flex items-start gap-2">
              <span className="w-20 shrink-0 text-xs text-zinc-400 tabular-nums">{n.date}</span>
              <Tag color={SENTIMENT[n.sentiment].color}>{SENTIMENT[n.sentiment].label}</Tag>
              <span className="min-w-0 flex-1">
                {n.title}
                <span className="ml-1 text-xs text-zinc-400">{n.source}</span>
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="工商信息">
        <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
          {rows.map(([k, v]) => (
            <div key={k} className="flex gap-2">
              <dt className="w-28 shrink-0 text-zinc-500">{k}</dt>
              <dd className="min-w-0 break-all">{v}</dd>
            </div>
          ))}
        </dl>
        <ul className="space-y-1">
          {d.risks.map((r) => (
            <li
              key={r.text}
              className={cn(
                "flex items-center gap-1.5 text-xs",
                r.level === "low" ? "text-zinc-500" : "text-amber-700",
              )}
            >
              <AlertTriangle className="size-3.5" />
              {r.text}
            </li>
          ))}
        </ul>
      </Section>
    </div>
  )
}
