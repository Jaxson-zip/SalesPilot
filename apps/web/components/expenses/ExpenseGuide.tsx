"use client"

import { BookOpen, ChevronDown } from "lucide-react"
import { useState } from "react"

import { QuickChips } from "@/components/biz/QuickChips"
import type { ExpenseGuide as Guide, ExpenseTemplate, ExpenseType } from "@/types/api"

/** 新建报销顶部：「从模板开始」快捷选项（选中后带出类型、交通方式和事由开头） */
export function ExpenseTemplatePicker({
  templates,
  active,
  onPick,
}: {
  templates: ExpenseTemplate[]
  active: string | null
  onPick: (tpl: ExpenseTemplate) => void
}) {
  if (templates.length === 0) return null
  return (
    <div className="space-y-1.5">
      <div className="text-zinc-500">从模板开始</div>
      <QuickChips
        label="报销模板"
        items={templates.map((t) => ({
          key: t.id,
          label: t.label,
          title: t.example ? `示例：${t.example}` : undefined,
        }))}
        active={active}
        onPick={(key) => {
          const tpl = templates.find((t) => t.id === key)
          if (tpl) onPick(tpl)
        }}
      />
    </div>
  )
}

/**
 * 「报销须知」：当前类型的报销标准、必填要求、需要的票据和制度出处（文字和数字都来自 /api/templates，
 * 数字由后端按 rules.yaml 计算）。默认展开一次，之后由用户自己折叠。
 */
export function ExpenseGuidePanel({ guides, type, example }: { guides: Guide[]; type: ExpenseType; example?: string }) {
  const [open, setOpen] = useState(true)
  const guide = guides.find((g) => g.type === type)
  if (!guide) return null
  return (
    <section className="rounded-lg border border-zinc-200 bg-zinc-50/60" aria-label="报销须知">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 w-full items-center gap-2 px-3 text-left font-medium text-zinc-700"
      >
        <BookOpen className="size-4 text-zinc-500" />
        <span className="flex-1">报销须知 · {guide.label}</span>
        <ChevronDown className={`size-4 text-zinc-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? (
        <dl className="space-y-1.5 px-3 pb-3 text-zinc-600">
          <GuideRow label="标准" value={guide.standard} />
          <GuideRow label="要求" value={guide.must} />
          <GuideRow label="票据" value={guide.attachments.join(" + ")} />
          {example ? <GuideRow label="事由示例" value={example} /> : null}
          <GuideRow label="依据" value={guide.rule_ref} />
        </dl>
      ) : null}
    </section>
  )
}

function GuideRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 gap-2">
      <dt className="w-16 shrink-0 text-zinc-400">{label}</dt>
      <dd className="min-w-0 break-words">{value}</dd>
    </div>
  )
}
