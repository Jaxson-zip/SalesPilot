"use client"

import { Check, Plus, X } from "lucide-react"
import { useState } from "react"

import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { formatFen } from "@/lib/format"
import {
  COMPLEXITIES,
  PLATFORMS,
  addModule,
  canConfirm,
  confirmedRequirement,
  hasOcr,
  parsePages,
  removeModule,
  togglePlatform,
  updateModule,
  type RequirementCardData,
} from "@/lib/requirement-card"
import { cn } from "@/lib/utils"

const CHIP = "inline-flex h-7 items-center gap-1 rounded-full border px-2.5 text-xs transition-colors"
const chip = (on: boolean) =>
  cn(CHIP, on ? "border-zinc-900 bg-zinc-900 text-white" : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50")

/** 小号分段选择（复杂度、首期 / 二期、交付方式） */
function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  disabled,
  label,
}: {
  value: T
  options: [T, string][]
  onChange: (v: T) => void
  disabled?: boolean
  label: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex shrink-0 rounded-md bg-zinc-100 p-0.5">
      {options.map(([v, text]) => (
        <button
          key={String(v)}
          type="button"
          role="radio"
          aria-checked={v === value}
          disabled={disabled}
          onClick={() => onChange(v)}
          className={cn(
            "h-6 rounded px-2 text-xs text-zinc-500 disabled:cursor-default",
            v === value && "bg-white font-medium text-zinc-900 shadow-xs",
          )}
        >
          {text}
        </button>
      ))}
    </div>
  )
}

/**
 * 需求确认卡片：AI 拆出的交付端和功能模块，销售和客户核对后增删、调整，确认后出三档正式报价。
 * readOnly：历史消息或已经确认过，只展示不能改。
 */
export function RequirementCard({
  data,
  onConfirm,
  readOnly,
}: {
  data: RequirementCardData
  onConfirm?: (requirement: Record<string, unknown>) => void
  readOnly?: boolean
}) {
  const [req, setReq] = useState(data.requirement)
  const [adding, setAdding] = useState("")
  const [sent, setSent] = useState(false)
  const locked = readOnly || sent || !onConfirm
  const solo = req.team_size === 1

  const add = () => {
    setReq((r) => addModule(r, adding))
    setAdding("")
  }
  const confirm = () => {
    if (!onConfirm || !canConfirm(req)) return
    setSent(true)
    onConfirm(confirmedRequirement(req))
  }

  return (
    <section aria-label="需求清单" className="rounded-xl border border-zinc-200 bg-white">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-zinc-100 px-3.5 py-2.5">
        <span className="font-medium">需求清单{req.project ? ` · ${req.project}` : ""}</span>
        <span className="text-xs text-zinc-500">
          粗估{" "}
          <span className="font-medium text-zinc-900 tabular-nums">
            {formatFen(data.price_low)}–{formatFen(data.price_high)}
          </span>
        </span>
      </div>

      <div className="space-y-3 px-3.5 py-3">
        {data.notes?.length ? (
          <ul
            aria-label="提醒"
            className="space-y-1 rounded-md bg-amber-50 px-2.5 py-2 text-xs leading-5 text-amber-900"
          >
            {data.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        ) : null}
        <div>
          <div className="mb-1.5 text-xs text-zinc-500">交付端</div>
          <div className="flex flex-wrap gap-1.5">
            {PLATFORMS.map(([p, name]) => {
              const on = req.platforms.includes(p)
              return (
                <button
                  key={p}
                  type="button"
                  aria-pressed={on}
                  disabled={locked}
                  onClick={() => setReq((r) => togglePlatform(r, p))}
                  className={cn(chip(on), "disabled:cursor-default")}
                >
                  {on ? <Check className="size-3" /> : null}
                  {name}
                </button>
              )
            })}
          </div>
        </div>

        <div>
          <div className="mb-1 text-xs text-zinc-500">功能模块（{req.modules.length}）</div>
          <ul className="divide-y divide-zinc-100">
            {req.modules.map((m, i) => (
              <li key={`${m.key}-${m.name}`} className="flex flex-wrap items-center gap-x-2 gap-y-1.5 py-1.5">
                {/* 窄屏：名称独占一行，复杂度 / 批次换到下一行 */}
                <div className="flex min-w-0 basis-full items-center gap-2 sm:flex-1 sm:basis-0">
                  <span className="min-w-0 truncate text-sm" title={m.name}>
                    {m.name}
                  </span>
                  {m.source === "inferred" ? <Tag color="yellow">AI 推断</Tag> : null}
                </div>
                <Segmented
                  label={`${m.name} 复杂度`}
                  value={m.complexity}
                  options={COMPLEXITIES}
                  disabled={locked}
                  onChange={(v) => setReq((r) => updateModule(r, i, { complexity: v }))}
                />
                <Segmented
                  label={`${m.name} 上线批次`}
                  value={m.must ? "must" : "later"}
                  options={[
                    ["must", "首期"],
                    ["later", "二期"],
                  ]}
                  disabled={locked}
                  onChange={(v) => setReq((r) => updateModule(r, i, { must: v === "must" }))}
                />
                {locked ? null : (
                  <button
                    type="button"
                    aria-label={`删除 ${m.name}`}
                    onClick={() => setReq((r) => removeModule(r, i))}
                    className="inline-flex size-6 items-center justify-center rounded text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
                  >
                    <X className="size-3.5" />
                  </button>
                )}
              </li>
            ))}
          </ul>
          {locked ? null : (
            <form
              className="mt-1.5 flex gap-1.5"
              onSubmit={(e) => {
                e.preventDefault()
                add()
              }}
            >
              <Input
                value={adding}
                onChange={(e) => setAdding(e.target.value)}
                placeholder="补充功能，例如「会员积分」"
                aria-label="补充功能"
                className="h-8 text-base md:text-sm"
              />
              <Button type="submit" variant="outline" size="sm" disabled={!adding.trim()}>
                <Plus />
                添加
              </Button>
            </form>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-zinc-500">交付方式</span>
          <Segmented
            label="交付方式"
            value={solo ? "solo" : "team"}
            options={[
              ["team", "团队"],
              ["solo", "个人全栈"],
            ]}
            disabled={locked}
            onChange={(v) => setReq((r) => ({ ...r, team_size: v === "solo" ? 1 : null }))}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-zinc-500">流程文档</span>
          <Segmented
            label="流程文档"
            value={req.no_sop ? "none" : "has"}
            options={[
              ["has", "客户已有"],
              ["none", "没有，需要梳理"],
            ]}
            disabled={locked}
            onChange={(v) => setReq((r) => ({ ...r, no_sop: v === "none" ? true : null }))}
          />
        </div>

        {hasOcr(req) ? (
          <label className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-zinc-500">每月识别量</span>
            <Input
              inputMode="numeric"
              disabled={locked}
              value={req.ocr_monthly_pages ?? ""}
              onChange={(e) => setReq((r) => ({ ...r, ocr_monthly_pages: parsePages(e.target.value) }))}
              placeholder="不填按默认月量估"
              aria-label="每月识别量（张）"
              className="h-7 w-36 text-sm"
            />
            <span className="text-xs text-zinc-500">张 / 月</span>
          </label>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-100 px-3.5 py-2.5">
        <span className="text-xs text-zinc-500">
          {sent ? "已确认，正在生成正式报价" : "价格按模块人天由报价引擎计算，确认后生成三档报价"}
        </span>
        {locked ? null : (
          <Button size="sm" onClick={confirm} disabled={!canConfirm(req)}>
            确认需求，出报价
          </Button>
        )}
      </div>
    </section>
  )
}
