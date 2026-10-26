"use client"

import { ArrowLeft, Printer } from "lucide-react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useEffect, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"

import { QueryError } from "@/components/biz/QueryStatus"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useQuote } from "@/hooks/useQuotes"
import { formatFen, formatPercent } from "@/lib/format"
import { useTemplates } from "@/hooks/useTemplates"
import { PRINT_COMPANY, printDocTitle, printTotals } from "@/lib/quote-print"
import { fenToRmbUpper } from "@/lib/rmb"
import type { QuoteDetail } from "@/types/api"

const DEFAULT_NOTE = "以上报价以人民币计价。如需调整配置或数量，请联系您的客户经理。"

/** 打印页铺满视口盖住应用外壳（屏幕上是 A4 预览）；打印时 print CSS 只输出 .print-root */
function PrintPortal({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  if (!mounted) return null
  return createPortal(
    <div className="print-root fixed inset-0 z-50 overflow-y-auto bg-zinc-100">{children}</div>,
    document.body,
  )
}

function Meta({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="w-16 shrink-0 text-zinc-500">{label}</span>
      <span className="min-w-0 break-words">{value}</span>
    </div>
  )
}

/** 条款与说明：来自 /api/templates（有效期天数由后端按 rules.yaml 填入），管理员改 templates.yaml 即可调整 */
function QuoteTerms() {
  const terms = useTemplates().data?.quote_terms ?? []
  if (terms.length === 0) return null
  return (
    <section className="mt-6" aria-label="条款与说明">
      <div className="font-medium">条款与说明</div>
      <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-zinc-700">
        {terms.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ol>
    </section>
  )
}

function QuoteSheet({ q, showUpper }: { q: QuoteDetail; showUpper: boolean }) {
  const [note, setNote] = useState(DEFAULT_NOTE)
  const t = printTotals(q)
  return (
    <div className="print-sheet mx-auto my-6 min-h-[297mm] w-[210mm] max-w-full bg-white p-[16mm] text-[12px] leading-relaxed text-zinc-900 shadow-sm">
      <div className="flex items-end justify-between border-b-2 border-zinc-900 pb-3">
        <div className="text-lg font-semibold">{PRINT_COMPANY}</div>
        <div className="text-2xl font-semibold tracking-[0.3em]">报价单</div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-1.5">
        <Meta label="客户" value={q.customer?.name ?? "—"} />
        <Meta label="报价编号" value={q.code} />
        <Meta label="项目" value={q.opportunity?.name ?? "—"} />
        <Meta label="报价日期" value={q.created_at.slice(0, 10)} />
        <Meta label="方案" value={q.tier_name || q.tier || "—"} />
        <Meta label="有效期至" value={q.valid_until ? q.valid_until.slice(0, 10) : "—"} />
      </div>
      <table className="mt-5 w-full table-fixed border-collapse">
        <thead>
          <tr className="bg-zinc-100 text-left">
            <th className="w-10 border border-zinc-300 px-2 py-1.5 font-medium">序号</th>
            <th className="border border-zinc-300 px-2 py-1.5 font-medium">项目</th>
            <th className="w-12 border border-zinc-300 px-2 py-1.5 font-medium">单位</th>
            <th className="w-14 border border-zinc-300 px-2 py-1.5 text-right font-medium">数量</th>
            <th className="w-24 border border-zinc-300 px-2 py-1.5 text-right font-medium">单价</th>
            <th className="w-28 border border-zinc-300 px-2 py-1.5 text-right font-medium">金额</th>
          </tr>
        </thead>
        <tbody>
          {q.items.map((it, i) => (
            <tr key={it.sku}>
              <td className="border border-zinc-300 px-2 py-1.5 tabular-nums">{i + 1}</td>
              <td className="border border-zinc-300 px-2 py-1.5 break-words">{it.name}</td>
              <td className="border border-zinc-300 px-2 py-1.5">{it.unit}</td>
              <td className="border border-zinc-300 px-2 py-1.5 text-right tabular-nums">{it.qty}</td>
              <td className="border border-zinc-300 px-2 py-1.5 text-right tabular-nums">{formatFen(it.unit_price)}</td>
              <td className="border border-zinc-300 px-2 py-1.5 text-right tabular-nums">
                {formatFen(it.subtotal_price)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 ml-auto w-72 space-y-1">
        <div className="flex justify-between">
          <span className="text-zinc-500">小计</span>
          <span className="tabular-nums">{formatFen(t.subtotal)}</span>
        </div>
        {t.discountAmount > 0 ? (
          <div className="flex justify-between">
            <span className="text-zinc-500">折扣（{formatPercent(t.discountRate)}）</span>
            <span className="tabular-nums">-{formatFen(t.discountAmount)}</span>
          </div>
        ) : null}
        <div className="flex justify-between border-t border-zinc-300 pt-1 text-sm font-semibold">
          <span>合计</span>
          <span className="tabular-nums">{formatFen(t.total)}</span>
        </div>
        {showUpper ? (
          <div className="flex justify-between gap-3">
            <span className="shrink-0 text-zinc-500">大写</span>
            <span className="text-right">{fenToRmbUpper(t.total)}</span>
          </div>
        ) : null}
      </div>
      <QuoteTerms />
      <div className="mt-4">
        <label htmlFor="print-note" className="font-medium">
          备注
        </label>
        <Textarea
          id="print-note"
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="mt-1 resize-none text-[12px] print:border-0 print:p-0 print:shadow-none"
        />
      </div>
      <div className="mt-12 grid grid-cols-2 gap-10">
        {["报价方（盖章）", "客户确认（盖章）"].map((who) => (
          <div key={who} className="space-y-6">
            <div className="font-medium">{who}</div>
            <div className="border-b border-zinc-400 pb-1 text-zinc-500">签字：</div>
            <div className="border-b border-zinc-400 pb-1 text-zinc-500">日期：</div>
          </div>
        ))}
      </div>
    </div>
  )
}

/** 正式报价单打印页（v3 §14）：A4 版式，不显示成本和毛利；「打印 / 存为PDF」调用浏览器打印 */
export default function QuotePrintPage() {
  const { id } = useParams<{ id: string }>()
  const quoteId = decodeURIComponent(id)
  const query = useQuote(quoteId)
  const [showUpper, setShowUpper] = useState(true)
  const q = query.data

  // 浏览器「存为 PDF」默认用页面标题作文件名
  useEffect(() => {
    if (!q) return
    const prev = document.title
    document.title = printDocTitle(q)
    return () => {
      document.title = prev
    }
  }, [q])

  let body
  if (query.isPending) body = <Skeleton className="mx-auto my-6 h-[600px] w-[210mm] max-w-full" />
  else if (query.isError)
    body = (
      <div className="mx-auto my-6 max-w-xl rounded-lg bg-white">
        <QueryError error={query.error} onRetry={() => void query.refetch()} feature="报价单" />
      </div>
    )
  else body = <QuoteSheet q={query.data} showUpper={showUpper} />

  return (
    <PrintPortal>
      <div className="no-print sticky top-0 z-10 flex h-12 items-center gap-2 border-b border-zinc-200 bg-white px-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/quotes/${encodeURIComponent(quoteId)}`}>
            <ArrowLeft />
            返回报价单
          </Link>
        </Button>
        <span className="min-w-0 flex-1 truncate text-zinc-500">{q ? printDocTitle(q) : "报价单"}</span>
        <label className="flex items-center gap-2 text-zinc-600">
          <Checkbox checked={showUpper} onCheckedChange={(v) => setShowUpper(v === true)} aria-label="显示大写金额" />
          <span className="max-sm:hidden">显示大写金额</span>
        </label>
        {q ? (
          <Button size="sm" onClick={() => window.print()}>
            <Printer />
            打印 / 存为 PDF
          </Button>
        ) : null}
      </div>
      {body}
    </PrintPortal>
  )
}
