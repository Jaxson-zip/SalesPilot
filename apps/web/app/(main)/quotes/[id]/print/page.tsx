"use client"

import { ArrowLeft, Printer } from "lucide-react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useState } from "react"

import {
  ItemsTable,
  Meta,
  PrintHeader,
  PrintPaper,
  PrintPortal,
  Signatures,
  TermsList,
  useDocTitle,
} from "@/components/biz/PrintSheet"
import { QueryError } from "@/components/biz/QueryStatus"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useQuote } from "@/hooks/useQuotes"
import { useOpportunityRequirement } from "@/hooks/useRequirement"
import { formatFen, formatPercent } from "@/lib/format"
import { useTemplates } from "@/hooks/useTemplates"
import { PRINT_COMPANY, printDocTitle, printScope, printTotals } from "@/lib/quote-print"
import { fenToRmbUpper } from "@/lib/rmb"
import type { QuoteDetail } from "@/types/api"

const DEFAULT_NOTE = "以上报价以人民币计价。如需调整配置或数量，请联系您的客户经理。"

/** 条款与说明：来自 /api/templates（有效期天数由后端按 rules.yaml 填入），管理员改 templates.yaml 即可调整 */
function QuoteTerms() {
  const terms = useTemplates().data?.quote_terms ?? []
  return <TermsList title="条款与说明" terms={terms} />
}

/** 项目范围：只在商机上有「已确认」的需求清单时显示（软件外包），说明交付端、交付方式和本期不含的功能 */
function ProjectScope({ q }: { q: QuoteDetail }) {
  const { data } = useOpportunityRequirement(q.opportunity?.id ?? null)
  if (!data?.confirmed || data.pack !== q.pack) return null
  const s = printScope(data.data, q.items)
  return (
    <section className="mt-4 space-y-1" aria-label="项目范围">
      <div className="font-medium">项目范围</div>
      <Meta label="交付端" value={s.platforms || "—"} />
      <Meta label="交付方式" value={s.delivery === "个人全栈" ? "个人全栈开发" : "项目团队开发"} />
      <Meta label="功能清单" value="见下表各功能模块，以表内列出的为准" />
      {s.excluded.length > 0 ? (
        <Meta label="本期不含" value={`${s.excluded.join("、")}（可作为二期另行报价）`} />
      ) : null}
    </section>
  )
}

function QuoteSheet({ q, showUpper }: { q: QuoteDetail; showUpper: boolean }) {
  const [note, setNote] = useState(DEFAULT_NOTE)
  const t = printTotals(q)
  return (
    <PrintPaper>
      <PrintHeader company={PRINT_COMPANY} title="报价单" />
      <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-1.5">
        <Meta label="客户" value={q.customer?.name ?? "—"} />
        <Meta label="报价编号" value={q.code} />
        <Meta label="项目" value={q.opportunity?.name ?? "—"} />
        <Meta label="报价日期" value={q.created_at.slice(0, 10)} />
        <Meta label="方案" value={q.tier_name || q.tier || "—"} />
        <Meta label="有效期至" value={q.valid_until ? q.valid_until.slice(0, 10) : "—"} />
      </div>
      <ProjectScope q={q} />
      <div className="mt-5">
        <ItemsTable items={q.items} />
      </div>
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
      <Signatures parties={["报价方（盖章）", "客户确认（盖章）"]} />
    </PrintPaper>
  )
}

/** 正式报价单打印页（v3 §14）：A4 版式，不显示成本和毛利；「打印 / 存为PDF」调用浏览器打印 */
export default function QuotePrintPage() {
  const { id } = useParams<{ id: string }>()
  const quoteId = decodeURIComponent(id)
  const query = useQuote(quoteId)
  const [showUpper, setShowUpper] = useState(true)
  const q = query.data

  useDocTitle(q ? printDocTitle(q) : null)

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
