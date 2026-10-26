import { ChevronRight, FileText } from "lucide-react"
import Link from "next/link"

import { Tag } from "@/components/biz/Tag"
import { type CoreQuote, QUOTE_STATUS } from "@/lib/artifacts"
import { formatFen, formatPercent } from "@/lib/format"

/** Agent 写入报价单后的结果卡片：编号、状态、金额、毛利，点击进入报价单详情 */
export function QuoteCard({ quote }: { quote: CoreQuote }) {
  const status = QUOTE_STATUS[quote.status] ?? { label: quote.status, color: "gray" as const }
  return (
    <Link
      href={`/quotes/${quote.id}`}
      className="flex min-w-0 items-center gap-3 rounded-xl border border-zinc-200 bg-white px-3.5 py-3 text-sm hover:border-zinc-300 hover:bg-zinc-50"
    >
      <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-zinc-100">
        <FileText className="size-4 text-zinc-600" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-medium">报价单 {quote.code}</span>
          <Tag color={status.color}>{status.label}</Tag>
        </div>
        <div className="mt-0.5 text-xs text-zinc-500 tabular-nums">
          {formatFen(quote.total_price)} · 毛利 {formatPercent(quote.margin_rate)}
        </div>
      </div>
      <ChevronRight className="size-4 shrink-0 text-zinc-400" />
    </Link>
  )
}
