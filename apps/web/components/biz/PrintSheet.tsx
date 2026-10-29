"use client"

import { useEffect, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"

import { formatFen } from "@/lib/format"
import type { QuoteLine } from "@/types/api"

/** 打印页铺满视口盖住应用外壳（屏幕上是 A4 预览）；打印时 print CSS 只输出 .print-root */
export function PrintPortal({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  if (!mounted) return null
  return createPortal(
    <div className="print-root fixed inset-0 z-50 overflow-y-auto bg-zinc-100">{children}</div>,
    document.body,
  )
}

/** A4 纸面 */
export function PrintPaper({ children }: { children: ReactNode }) {
  return (
    <div className="print-sheet mx-auto my-6 min-h-[297mm] w-[210mm] max-w-full bg-white p-[16mm] text-[12px] leading-relaxed text-zinc-900 shadow-sm">
      {children}
    </div>
  )
}

export function PrintHeader({ company, title }: { company: string; title: string }) {
  return (
    <div className="flex items-end justify-between border-b-2 border-zinc-900 pb-3">
      <div className="text-lg font-semibold">{company}</div>
      <div className="text-2xl font-semibold tracking-[0.3em]">{title}</div>
    </div>
  )
}

export function Meta({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="w-16 shrink-0 text-zinc-500">{label}</span>
      <span className="min-w-0 break-words">{value}</span>
    </div>
  )
}

const TD = "border border-zinc-300 px-2 py-1.5"

/** 报价明细表（不含成本和毛利） */
export function ItemsTable({ items }: { items: QuoteLine[] }) {
  return (
    <table className="w-full table-fixed border-collapse">
      <thead>
        <tr className="bg-zinc-100 text-left">
          <th className={`w-12 ${TD} font-medium whitespace-nowrap`}>序号</th>
          <th className={`${TD} font-medium`}>项目</th>
          <th className={`w-12 ${TD} font-medium`}>单位</th>
          <th className={`w-14 ${TD} text-right font-medium`}>数量</th>
          <th className={`w-24 ${TD} text-right font-medium`}>单价</th>
          <th className={`w-28 ${TD} text-right font-medium`}>金额</th>
        </tr>
      </thead>
      <tbody>
        {items.map((it, i) => (
          <tr key={it.sku}>
            <td className={`${TD} tabular-nums`}>{i + 1}</td>
            <td className={`${TD} break-words`}>{it.name}</td>
            <td className={TD}>{it.unit}</td>
            <td className={`${TD} text-right tabular-nums`}>{it.qty}</td>
            <td className={`${TD} text-right tabular-nums`}>{formatFen(it.unit_price)}</td>
            <td className={`${TD} text-right tabular-nums`}>{formatFen(it.subtotal_price)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function TermsList({ title, terms, label }: { title: string; terms: string[]; label?: string }) {
  if (terms.length === 0) return null
  return (
    <section className="mt-6" aria-label={label ?? title}>
      <div className="font-medium">{title}</div>
      <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-zinc-700">
        {terms.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ol>
    </section>
  )
}

/** 底部签字盖章栏 */
export function Signatures({ parties }: { parties: string[] }) {
  return (
    <div className="mt-12 grid grid-cols-2 gap-10">
      {parties.map((who) => (
        <div key={who} className="space-y-6">
          <div className="font-medium">{who}</div>
          <div className="border-b border-zinc-400 pb-1 text-zinc-500">签字：</div>
          <div className="border-b border-zinc-400 pb-1 text-zinc-500">日期：</div>
        </div>
      ))}
    </div>
  )
}

/** 浏览器「存为 PDF」默认用页面标题作文件名 */
export function useDocTitle(title: string | null) {
  useEffect(() => {
    if (!title) return
    const prev = document.title
    document.title = title
    return () => {
      document.title = prev
    }
  }, [title])
}
