"use client"

import { Check, Plus, RotateCcw, Save, Trash2, TriangleAlert } from "lucide-react"
import { useState } from "react"
import { Section, Line, CatalogPicker, EXTRA_KINDS, LabeledInput, Row } from "@/components/quotes/QuoteAdjustParts"

import { SimpleSelect } from "@/components/biz/FormControls"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group"
import { usePackDetail } from "@/hooks/useProductLines"
import { useAdjustQuote } from "@/hooks/useQuotes"
import { useSession } from "@/components/shell/SessionProvider"
import { quoteApprovalHint } from "@/lib/confirm-texts"
import { formatFen, formatPercent } from "@/lib/format"
import { yuanToFen } from "@/lib/money"
import {
  catalogRow,
  discountToInput,
  initialDraft,
  isAdjustDirty,
  newExtraRow,
  approvalPreview,
  approvalRules,
  previewAdjust,
  toItemsPatch,
  type DraftRow,
} from "@/lib/quote-adjust"
import { cn } from "@/lib/utils"
import type { QuoteDetail, QuoteItemsPatch } from "@/types/api"

/**
 * 草稿报价单调价（v3 §14）。父组件用 key 绑定报价内容，保存成功后重新挂载以载入后端结果。
 */
export function QuoteAdjust({ q }: { q: QuoteDetail }) {
  const adjust = useAdjustQuote(q.id)
  return (
    <QuoteEditor
      title={`${q.tier_name || "方案"} · 物料清单`}
      pack={q.pack}
      initial={initialDraft(q.items)}
      initialDiscount={discountToInput(q.discount_rate)}
      isDirty={(rows, discount) => isAdjustDirty(q.items, rows, discount, q.discount_rate)}
      saved={{ total: q.total_price, margin: q.margin_rate }}
      saving={adjust.isPending}
      saveLabel="保存调整"
      onSave={(body) => adjust.mutate(body)}
    />
  )
}

/**
 * 报价明细编辑：目录物料改单价、数量，从目录添加；目录以外的费用（加急、差旅、第三方服务等）自己填；
 * 整单折扣。输入后实时预览合计和预估毛利，保存后总价、毛利、是否需要审批以后端返回为准。
 */
export function QuoteEditor({
  title,
  pack,
  initial,
  initialDiscount = "",
  isDirty,
  saved,
  saving,
  saveLabel,
  onSave,
}: {
  title: string
  pack: string
  initial: DraftRow[]
  initialDiscount?: string
  /** 和保存过的内容比有没有改动；新建时不传（有明细就能保存） */
  isDirty?: (rows: DraftRow[], discount: string) => boolean
  /** 已保存的合计和毛利（没改动时显示）；新建时不传 */
  saved?: { total: number; margin: number }
  saving: boolean
  saveLabel: string
  onSave: (body: QuoteItemsPatch) => void
}) {
  const { solo } = useSession()
  const [rows, setRows] = useState<DraftRow[]>(initial)
  const [discount, setDiscount] = useState(initialDiscount)
  const detail = usePackDetail(pack).data
  const catalog = detail?.catalog ?? []
  const preview = previewAdjust(rows, discount)
  // 提交后会不会进审批：和后端同一套规则（毛利底线、按目录价算的折扣权限）
  const rules = approvalRules(detail?.rules)
  const approval =
    rules && rows.length
      ? approvalPreview(rows, discount, Object.fromEntries(catalog.map((c) => [c.sku, c.price])), rules)
      : null
  const dirty = isDirty ? isDirty(rows, discount) : rows.length > 0
  const subtotal = new Map(preview.lines.map((l) => [l.sku, l.subtotal]))
  const items = rows.filter((r) => !r.extra)
  const extras = rows.filter((r) => r.extra)
  const showSaved = saved && !dirty
  const margin = showSaved ? saved.margin : preview.margin

  const edit = (sku: string, patch: Partial<DraftRow>) =>
    setRows((all) => all.map((r) => (r.sku === sku ? { ...r, ...patch } : r)))
  const remove = (sku: string) => setRows((all) => all.filter((r) => r.sku !== sku))
  const reset = () => {
    setRows(initial)
    setDiscount(initialDiscount)
  }
  const save = () => {
    const body = toItemsPatch(rows, discount)
    if (body) onSave(body)
  }
  const del = (r: DraftRow, label: string) => (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={`删除${label}`}
      className="text-zinc-400 hover:text-red-600"
      onClick={() => remove(r.sku)}
    >
      <Trash2 />
    </Button>
  )
  const sub = (r: DraftRow) => (
    <span className="ml-auto w-24 text-right tabular-nums">{formatFen(subtotal.get(r.sku))}</span>
  )

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200">
      <div className="flex h-10 items-center justify-between border-b border-zinc-200 bg-zinc-50 px-3.5">
        <span className="truncate font-medium">{title}</span>
        <span className="text-xs text-zinc-500">单价、数量都能改</span>
      </div>

      <Section
        label="物料"
        hint={items.length ? undefined : "从产品目录添加"}
        add={
          <CatalogPicker
            catalog={catalog.filter((c) => !rows.some((r) => r.sku === c.sku))}
            onPick={(c) =>
              setRows((all) => [...all.filter((r) => !r.extra), catalogRow(c), ...all.filter((r) => r.extra)])
            }
          />
        }
      >
        {items.map((r) => {
          const price = yuanToFen(r.price)
          const changed = r.basePrice !== null && price !== null && price !== r.basePrice
          return (
            <Line key={r.sku}>
              <div className="min-w-40 flex-1">
                <p className="break-words">{r.name}</p>
                {changed ? <p className="text-xs text-amber-700">原价 {formatFen(r.basePrice)}</p> : null}
              </div>
              <LabeledInput
                label={`单价：${r.name}`}
                prefix="单价"
                placeholder="元"
                value={r.price}
                onChange={(v) => edit(r.sku, { price: v })}
              />
              <LabeledInput
                label={`数量：${r.name}`}
                prefix="数量"
                placeholder="1"
                suffix={r.unit}
                numeric
                className="w-32"
                value={r.qty}
                onChange={(v) => edit(r.sku, { qty: v })}
              />
              {sub(r)}
              {del(r, r.name)}
            </Line>
          )
        })}
      </Section>

      <Section
        label="额外费用"
        hint="目录里没有的：加急、实施服务；替客户垫付的差旅、采购选「代垫费用」"
        add={
          <Button variant="outline" size="sm" onClick={() => setRows((all) => [...all, newExtraRow()])}>
            <Plus />
            添加费用
          </Button>
        }
      >
        {extras.map((r, i) => (
          <Line key={r.sku}>
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
              className="w-32"
              value={r.price}
              onChange={(v) => edit(r.sku, { price: v })}
            />
            <SimpleSelect<"service" | "passthrough">
              ariaLabel={`费用类型 ${i + 1}`}
              size="sm"
              className="w-24"
              value={r.passthrough ? "passthrough" : "service"}
              onChange={(v) => edit(r.sku, { passthrough: v === "passthrough" })}
              options={EXTRA_KINDS}
            />
            {r.passthrough ? (
              <span
                className="w-32 text-xs text-zinc-500"
                title="替客户垫付的钱按实际花费收回：成本 = 单价，不打折、不计提成、不算进毛利率"
              >
                按成本价收，不计提成
              </span>
            ) : (
              <LabeledInput
                label={`成本 ${i + 1}`}
                prefix="成本"
                placeholder="可不填"
                className="w-32"
                title="这笔费用自己要付出去的钱（如差旅实际花费），用来算毛利；不填按 0"
                value={r.cost}
                onChange={(v) => edit(r.sku, { cost: v })}
              />
            )}
            <LabeledInput
              label={`数量 ${i + 1}`}
              prefix="数量"
              placeholder="1"
              numeric
              className="w-20"
              value={r.qty}
              onChange={(v) => edit(r.sku, { qty: v })}
            />
            {sub(r)}
            {del(r, `费用 ${i + 1}`)}
          </Line>
        ))}
      </Section>

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
              aria-invalid={preview.valid || !rows.length ? undefined : true}
              onChange={(e) => setDiscount(e.target.value)}
            />
            <InputGroupAddon align="inline-end">
              <InputGroupText>%</InputGroupText>
            </InputGroupAddon>
          </InputGroup>
        </div>
        <Row label="折前合计" value={formatFen(preview.listTotal)} />
        <Row label="折扣" value={preview.discountAmount ? `-${formatFen(preview.discountAmount)}` : "—"} />
        {preview.passthroughTotal ? (
          <Row label="其中代垫费用" value={formatFen(preview.passthroughTotal)} hint="原价收，不打折" />
        ) : null}
        <Row
          label={showSaved ? "报价合计" : "预览合计"}
          value={formatFen(showSaved ? saved.total : preview.total)}
          strong
          hint={showSaved ? undefined : "保存后以系统计算为准"}
        />
        <Row
          label={showSaved ? "毛利率" : "预估毛利率"}
          value={margin === null ? "—" : formatPercent(margin)}
          danger={margin !== null && margin < 0}
          hint={margin !== null && margin < 0 ? "低于成本" : undefined}
        />
        {approval ? (
          <p
            role="status"
            aria-label="审批预判"
            className={cn(
              "flex items-start gap-1.5 rounded-md px-2.5 py-2 text-xs",
              approval.length ? "bg-amber-50 text-amber-800" : "bg-zinc-50 text-zinc-500",
            )}
          >
            {approval.length ? (
              <TriangleAlert className="mt-px size-3.5 shrink-0" />
            ) : (
              <Check className="mt-px size-3.5 shrink-0" />
            )}
            <span>{quoteApprovalHint(approval, solo)}</span>
          </p>
        ) : null}
        {preview.onlyPassthrough ? (
          <p className="text-xs text-red-600">报价不能只有代垫费用，至少要有一项物料或服务</p>
        ) : rows.length && !preview.valid ? (
          <p className="text-xs text-red-600">单价为金额、数量为正整数；折扣为 0–99.9 的百分比；额外费用要填名称</p>
        ) : null}
        {dirty ? (
          <div className="flex justify-end gap-2 pt-1">
            {isDirty ? (
              <Button variant="outline" size="sm" onClick={reset} disabled={saving}>
                <RotateCcw />
                撤销修改
              </Button>
            ) : null}
            <Button size="sm" onClick={save} disabled={!preview.valid || saving}>
              <Save />
              {saving ? "保存中…" : saveLabel}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
