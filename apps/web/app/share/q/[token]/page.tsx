"use client"

import { FileText, Printer } from "lucide-react"
import { useParams } from "next/navigation"

import { ClientCostsTable, TermsList, useDocTitle } from "@/components/biz/PrintSheet"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { usePublicQuote, type PublicQuote } from "@/hooks/useQuoteShare"
import { isApiError } from "@/lib/api"
import { formatFen, formatPercent } from "@/lib/format"
import { PRINT_COMPANY, printScope } from "@/lib/quote-print"
import { fenToRmbUpper } from "@/lib/rmb"

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <div className="flex gap-3 py-1">
      <span className="w-16 shrink-0 text-zinc-500">{label}</span>
      <span className="min-w-0 break-words text-zinc-900">{value}</span>
    </div>
  )
}

function Scope({ q }: { q: PublicQuote }) {
  if (!q.scope) return null
  const req = { ...q.scope, modules: (q.scope.modules ?? []).map((name) => ({ name })) }
  const s = printScope(req, q.items)
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-4" aria-label="项目范围">
      <h2 className="mb-1 text-sm font-semibold">项目范围</h2>
      <Row label="交付端" value={s.platforms} />
      <Row label="交付方式" value={s.delivery === "个人全栈" ? "个人全栈开发" : "项目团队开发"} />
      {s.excluded.length > 0 ? <Row label="本期不含" value={`${s.excluded.join("、")}（可作为二期另行报价）`} /> : null}
    </section>
  )
}

function Items({ q }: { q: PublicQuote }) {
  const discount = Math.max(0, q.list_price - q.total_price)
  return (
    <section className="rounded-lg border border-zinc-200 bg-white" aria-label="报价明细">
      <h2 className="px-4 pt-4 text-sm font-semibold">报价明细</h2>
      <ul className="divide-y divide-zinc-100">
        {q.items.map((it, i) => (
          <li key={`${it.name}-${i}`} className="flex items-start justify-between gap-3 px-4 py-3">
            <div className="min-w-0">
              <div className="break-words text-zinc-900">{it.name}</div>
              <div className="mt-0.5 text-xs text-zinc-500 tabular-nums">
                {formatFen(it.unit_price)} × {it.qty} {it.unit}
              </div>
            </div>
            <div className="shrink-0 tabular-nums">{formatFen(it.subtotal_price)}</div>
          </li>
        ))}
      </ul>
      <div className="space-y-1 border-t border-zinc-200 px-4 py-3">
        {discount > 0 ? (
          <>
            <div className="flex justify-between text-zinc-500">
              <span>小计</span>
              <span className="tabular-nums">{formatFen(q.list_price)}</span>
            </div>
            <div className="flex justify-between text-zinc-500">
              <span>折扣（{formatPercent(q.discount_rate || discount / q.list_price)}）</span>
              <span className="tabular-nums">-{formatFen(discount)}</span>
            </div>
          </>
        ) : null}
        <div className="flex items-baseline justify-between">
          <span className="font-medium">合计</span>
          <span className="text-xl font-semibold tabular-nums">{formatFen(q.total_price)}</span>
        </div>
        <div className="text-right text-xs text-zinc-500">{fenToRmbUpper(q.total_price)}</div>
      </div>
    </section>
  )
}

function QuoteView({ q }: { q: PublicQuote }) {
  return (
    <div className="space-y-3">
      <header className="rounded-lg border border-zinc-200 bg-white p-4">
        <div className="text-xs text-zinc-500">{PRINT_COMPANY}</div>
        <h1 className="mt-1 text-lg font-semibold">{q.opportunity_name ?? "报价单"}</h1>
        {q.status === "accepted" ? (
          <div className="mt-2 inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">
            已确认成交
          </div>
        ) : null}
        <div className="mt-2 text-sm">
          <Row label="客户" value={q.customer_name} />
          <Row label="报价编号" value={q.code} />
          <Row label="方案" value={q.tier_name} />
          <Row label="报价日期" value={q.created_at.slice(0, 10)} />
          <Row label="有效期至" value={q.valid_until.slice(0, 10)} />
          <Row label="联系人" value={q.owner_name} />
        </div>
      </header>
      <Scope q={q} />
      <Items q={q} />
      {(q.client_costs ?? []).length > 0 ? (
        <section className="rounded-lg border border-zinc-200 bg-white p-4 text-xs">
          <ClientCostsTable costs={q.client_costs ?? []} title="运营期客户自付费用预估（不含在本报价内，实报实销）" />
        </section>
      ) : null}
      {(q.terms ?? []).length > 0 ? (
        <section className="rounded-lg border border-zinc-200 bg-white px-4 pb-4 text-xs">
          <TermsList title="条款与说明" terms={q.terms ?? []} />
        </section>
      ) : null}
      <p className="px-1 text-xs text-zinc-400">对报价有疑问或想调整，直接联系{q.owner_name ?? "发送人"}即可。</p>
    </div>
  )
}

/** 发给客户的报价分享页（契约 §35）：不需要登录，手机优先；只读，不含成本和毛利 */
export default function SharedQuotePage() {
  const { token } = useParams<{ token: string }>()
  const query = usePublicQuote(decodeURIComponent(token))
  const q = query.data
  useDocTitle(q ? ["报价单", q.code, q.customer_name].filter(Boolean).join("-") : null)

  let body
  if (query.isPending) body = <Skeleton className="h-96 w-full" />
  else if (query.isError) {
    const gone = isApiError(query.error) && query.error.code === 40401
    body = (
      <div className="rounded-lg border border-zinc-200 bg-white p-6 text-center">
        <FileText className="mx-auto size-8 text-zinc-300" />
        <div className="mt-3 font-medium">{gone ? "链接已失效" : "暂时打不开"}</div>
        <p className="mt-1 text-sm text-zinc-500">
          {gone ? "这条报价链接已过期或被撤销，请联系发送人重新获取。" : "网络好像有点问题，稍后刷新试试。"}
        </p>
      </div>
    )
  } else body = <QuoteView q={query.data} />

  return (
    <main className="min-h-dvh bg-zinc-50 text-sm">
      <div className="mx-auto max-w-2xl px-4 py-6">
        {body}
        {q ? (
          <div className="no-print mt-4 flex justify-center">
            <Button variant="outline" size="sm" onClick={() => window.print()}>
              <Printer />
              打印 / 存为 PDF
            </Button>
          </div>
        ) : null}
      </div>
    </main>
  )
}
