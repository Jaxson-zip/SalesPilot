"use client"

import { Plus, RotateCcw, Save, Trash2 } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group"
import { useAdjustQuote } from "@/hooks/useQuotes"
import { formatFen, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"
import {
  discountToInput,
  initialDraft,
  isAdjustDirty,
  newExtraRow,
  previewAdjust,
  toItemsPatch,
  type DraftRow,
} from "@/lib/quote-adjust"
import type { QuoteDetail } from "@/types/api"

/**
 * 草稿报价单调价（v3 §14）：数量、整单折扣可编辑，还能加目录以外的费用（加急、差旅、第三方服务等），
 * 输入后实时预览；「保存调整」后总价、毛利、是否需要审批以后端返回为准。
 * 父组件用 key 绑定报价内容，保存成功后重新挂载以载入后端结果。
 */
export function QuoteAdjust({ q }: { q: QuoteDetail }) {
  const [rows, setRows] = useState<DraftRow[]>(() => initialDraft(q.items))
  const [discount, setDiscount] = useState(() => discountToInput(q.discount_rate))
  const adjust = useAdjustQuote(q.id)
  const preview = previewAdjust(rows, discount)
  const dirty = isAdjustDirty(q.items, rows, discount, q.discount_rate)
  const subtotal = new Map(preview.lines.map((l) => [l.sku, l.subtotal]))
  const prices = new Map(q.items.map((it) => [it.sku, it.unit_price]))
  const catalog = rows.filter((r) => !r.extra)
  const extras = rows.filter((r) => r.extra)

  const edit = (sku: string, patch: Partial<DraftRow>) =>
    setRows((all) => all.map((r) => (r.sku === sku ? { ...r, ...patch } : r)))
  const remove = (sku: string) => setRows((all) => all.filter((r) => r.sku !== sku))
  const reset = () => {
    setRows(initialDraft(q.items))
    setDiscount(discountToInput(q.discount_rate))
  }
  const save = () => {
    const body = toItemsPatch(rows, discount)
    if (body) adjust.mutate(body)
  }

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200">
      <div className="flex h-10 items-center justify-between border-b border-zinc-200 bg-zinc-50 px-3.5">
        <span className="truncate font-medium">{q.tier_name || "方案"} · 物料清单</span>
        <span className="text-xs text-zinc-500">草稿可调整数量、折扣，加额外费用</span>
      </div>
      <table className="w-full table-fixed">
        <thead>
          <tr className="h-8 text-zinc-500">
            <th className="px-3.5 text-left font-normal">项目</th>
            <th className="hidden w-28 px-2 text-right font-normal sm:table-cell">单价</th>
            <th className="w-28 px-2 text-left font-normal">数量</th>
            <th className="w-28 px-3.5 text-right font-normal">小计</th>
          </tr>
        </thead>
        <tbody>
          {catalog.map((it) => (
            <tr key={it.sku} className="h-10 border-t border-zinc-100">
              <td className="px-3.5 py-1.5 break-words sm:truncate" title={it.name}>
                {it.name}
              </td>
              <td className="hidden px-2 text-right text-zinc-500 tabular-nums sm:table-cell">
                {formatFen(prices.get(it.sku))}
              </td>
              <td className="px-2">
                <div className="flex items-center gap-1.5">
                  <Input
                    id={`qty-${it.sku}`}
                    aria-label={`数量：${it.name}`}
                    inputMode="numeric"
                    className="h-7 w-16 px-2 tabular-nums"
                    value={it.qty}
                    onChange={(e) => edit(it.sku, { qty: e.target.value })}
                  />
                  <span className="truncate text-xs text-zinc-500">{it.unit}</span>
                </div>
              </td>
              <td className="px-3.5 text-right tabular-nums">{formatFen(subtotal.get(it.sku))}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <section aria-label="额外费用" className="space-y-2 border-t border-zinc-200 px-3.5 py-3">
        <div className="flex items-center justify-between gap-3">
          <span className="font-medium">额外费用</span>
          <span className="text-xs text-zinc-500">目录里没有的：加急、差旅、第三方服务等</span>
        </div>
        {extras.map((r, i) => (
          <div key={r.sku} className="flex flex-wrap items-center gap-2">
            <Input
              aria-label={`费用名称 ${i + 1}`}
              placeholder="名称，如加急实施费"
              className="h-8 min-w-40 flex-1"
              value={r.name}
              onChange={(e) => edit(r.sku, { name: e.target.value })}
            />
            <LabeledInput
              label={`单价 ${i + 1}`}
              prefix="单价"
              placeholder="元"
              value={r.price}
              onChange={(v) => edit(r.sku, { price: v })}
            />
            <LabeledInput
              label={`成本 ${i + 1}`}
              prefix="成本"
              placeholder="可不填"
              title="这笔费用自己要付出去的钱（如差旅实际花费），用来算毛利；不填按 0"
              value={r.cost}
              onChange={(v) => edit(r.sku, { cost: v })}
            />
            <LabeledInput
              label={`数量 ${i + 1}`}
              prefix="数量"
              placeholder="1"
              numeric
              className="w-24"
              value={r.qty}
              onChange={(v) => edit(r.sku, { qty: v })}
            />
            <span className="ml-auto w-24 text-right tabular-nums">{formatFen(subtotal.get(r.sku))}</span>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`删除费用 ${i + 1}`}
              className="text-zinc-400 hover:text-red-600"
              onClick={() => remove(r.sku)}
            >
              <Trash2 />
            </Button>
          </div>
        ))}
        <Button variant="outline" size="sm" onClick={() => setRows((all) => [...all, newExtraRow()])}>
          <Plus />
          添加费用
        </Button>
      </section>
      <div className="space-y-2 border-t border-zinc-200 px-3.5 py-3">
        <div className="flex items-center justify-between gap-3">
          <label htmlFor="quote-discount" className="text-zinc-500">
            整单折扣
          </label>
          <InputGroup className="w-28">
            <InputGroupInput
              id="quote-discount"
              inputMode="decimal"
              placeholder="0"
              className="text-right tabular-nums"
              value={discount}
              aria-invalid={preview.valid ? undefined : true}
              onChange={(e) => setDiscount(e.target.value)}
            />
            <InputGroupAddon align="inline-end">
              <InputGroupText>%</InputGroupText>
            </InputGroupAddon>
          </InputGroup>
        </div>
        <Row label="折前合计" value={formatFen(preview.listTotal)} />
        <Row label="折扣" value={preview.discountAmount ? `-${formatFen(preview.discountAmount)}` : "—"} />
        <Row
          label={dirty ? "预览合计" : "报价合计"}
          value={formatFen(dirty ? preview.total : q.total_price)}
          strong
          hint={dirty ? "预览，保存后以系统计算为准" : undefined}
        />
        <Row label="毛利率" value={formatPercent(q.margin_rate)} hint={dirty ? "保存后重新计算" : undefined} />
        {!preview.valid ? (
          <p className="text-xs text-red-600">数量为正整数；折扣为 0–99.9 的百分比；额外费用要填名称和单价</p>
        ) : null}
        {dirty ? (
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" size="sm" onClick={reset} disabled={adjust.isPending}>
              <RotateCcw />
              撤销修改
            </Button>
            <Button size="sm" onClick={save} disabled={!preview.valid || adjust.isPending}>
              <Save />
              {adjust.isPending ? "保存中…" : "保存调整"}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  )
}

/** 带前缀文字的小输入框（单价、成本、数量），输入后也看得出是哪一格 */
function LabeledInput({
  label,
  prefix,
  placeholder,
  title,
  numeric,
  className,
  value,
  onChange,
}: {
  label: string
  prefix: string
  placeholder: string
  title?: string
  numeric?: boolean
  className?: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <InputGroup className={cn("h-8 w-36", className)} title={title}>
      <InputGroupAddon>
        <InputGroupText>{prefix}</InputGroupText>
      </InputGroupAddon>
      <InputGroupInput
        aria-label={label}
        inputMode={numeric ? "numeric" : "decimal"}
        placeholder={placeholder}
        className="tabular-nums"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </InputGroup>
  )
}

function Row({ label, value, strong, hint }: { label: string; value: string; strong?: boolean; hint?: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-zinc-500">
        {label}
        {hint ? <span className="ml-1.5 text-xs text-zinc-400">{hint}</span> : null}
      </span>
      <span className={strong ? "font-semibold tabular-nums" : "tabular-nums"}>{value}</span>
    </div>
  )
}
