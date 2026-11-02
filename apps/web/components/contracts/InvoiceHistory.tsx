"use client"

import { formatFen, formatRelative } from "@/lib/format"
import { invoiceEventText } from "@/lib/invoice"
import type { InvoiceEvent } from "@/types/api"

/** 开票历史（申请、登记、作废，新的在前）：作废的原票号码、原因和操作人都留在这里 */
export function InvoiceHistory({ events }: { events: InvoiceEvent[] }) {
  if (!events.length) return null
  return (
    <section aria-label="开票历史" className="space-y-1.5">
      <h3 className="text-sm font-medium">开票历史</h3>
      <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200 text-sm">
        {events.map((e, i) => (
          <li key={`${e.created_at}-${i}`} className="px-3 py-2">
            <div className="break-words text-zinc-900">
              {e.plan_name} {formatFen(e.amount)} · {invoiceEventText(e)}
            </div>
            <div className="mt-0.5 text-xs text-zinc-500">
              {e.actor?.name ?? "—"} · {formatRelative(e.created_at)}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
