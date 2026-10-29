"use client"

import { AlertTriangle, CircleCheck, CircleDashed, CircleDot, Loader2, Sparkles } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import {
  useAssessMeddic,
  useMeddic,
  useSaveMeddic,
  type MeddicAssessOut,
  type MeddicItem,
  type MeddicKey,
  type MeddicStatus,
} from "@/hooks/useMeddic"
import { cn } from "@/lib/utils"

const STATUS: Record<MeddicStatus, { label: string; icon: typeof CircleCheck; className: string }> = {
  confirmed: { label: "已确认", icon: CircleCheck, className: "text-emerald-600" },
  partial: { label: "待验证", icon: CircleDot, className: "text-amber-500" },
  missing: { label: "缺失", icon: CircleDashed, className: "text-zinc-300" },
}
const STATUS_ORDER: MeddicStatus[] = ["confirmed", "partial", "missing"]

/** 单项：状态图标 + 名称 + 证据；未确认时显示一条建议问题；负责人点开可以改 */
function Row({ item, editable, oppId }: { item: MeddicItem; editable: boolean; oppId: string }) {
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<MeddicStatus>(item.status)
  const [evidence, setEvidence] = useState(item.evidence ?? "")
  const save = useSaveMeddic(oppId)
  const meta = STATUS[item.status]
  const Icon = meta.icon
  const start = () => {
    setStatus(item.status)
    setEvidence(item.evidence ?? "")
    setOpen(true)
  }
  return (
    <li className="py-2">
      <button
        type="button"
        disabled={!editable}
        onClick={() => (open ? setOpen(false) : start())}
        aria-label={`${item.label}：${meta.label}`}
        className={cn("flex w-full items-start gap-2 text-left", editable && "cursor-pointer")}
      >
        <Icon className={cn("mt-0.5 size-4 shrink-0", meta.className)} />
        <span className="w-20 shrink-0 font-medium">{item.label}</span>
        <span className="min-w-0 flex-1 text-zinc-600">
          {item.evidence ? (
            <span className="line-clamp-2">{item.evidence}</span>
          ) : (
            <span className="text-zinc-400">{item.hint}</span>
          )}
          {item.status !== "confirmed" && item.questions[0] ? (
            <span className="mt-0.5 block text-xs text-zinc-500">建议问：{item.questions[0]}</span>
          ) : null}
        </span>
        {item.risk ? (
          <span className="shrink-0 rounded bg-amber-50 px-1.5 text-xs text-amber-700">本阶段应确认</span>
        ) : null}
      </button>
      {open ? (
        <div className="mt-2 ml-6 space-y-2 rounded-lg border border-zinc-200 p-2.5">
          <div role="radiogroup" aria-label={`${item.label} 状态`} className="flex gap-1">
            {STATUS_ORDER.map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={status === s}
                onClick={() => setStatus(s)}
                className={cn(
                  "h-7 rounded-md px-2.5 text-xs",
                  status === s ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100",
                )}
              >
                {STATUS[s].label}
              </button>
            ))}
          </div>
          <Textarea
            rows={2}
            maxLength={500}
            value={evidence}
            aria-label={`${item.label} 证据`}
            placeholder={`依据，例如：${item.questions[0] ?? item.hint}`}
            onChange={(e) => setEvidence(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button size="xs" variant="ghost" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button
              size="xs"
              disabled={save.isPending}
              onClick={() =>
                save.mutate(
                  { [item.key]: { status, evidence: evidence.trim() || null } },
                  { onSuccess: () => setOpen(false) },
                )
              }
            >
              保存
            </Button>
          </div>
        </div>
      ) : null}
    </li>
  )
}

/** AI 评估结果：逐项列出建议，负责人一键采纳（只采纳比现在更进一步或补了证据的项） */
function Assessment({
  result,
  items,
  editable,
  oppId,
  onClose,
}: {
  result: MeddicAssessOut
  items: MeddicItem[]
  editable: boolean
  oppId: string
  onClose: () => void
}) {
  const save = useSaveMeddic(oppId)
  const byKey = new Map(items.map((i) => [i.key, i]))
  const rank = (s: MeddicStatus) => STATUS_ORDER.length - STATUS_ORDER.indexOf(s)
  const useful = result.items.filter((s) => {
    const cur = byKey.get(s.key)
    return cur && (rank(s.status) > rank(cur.status) || (s.evidence && !cur.evidence))
  })
  const apply = () => {
    const patch: Partial<Record<MeddicKey, { status: MeddicStatus; evidence: string | null }>> = {}
    for (const s of useful) patch[s.key] = { status: s.status, evidence: s.evidence ?? null }
    save.mutate(patch, { onSuccess: onClose })
  }
  return (
    <div className="space-y-2 rounded-lg border border-violet-200 bg-violet-50/50 p-3">
      <div className="flex items-center gap-1.5 font-medium text-violet-800">
        <Sparkles className="size-4" />
        {result.source === "ai" ? "AI 评估" : "按跟进记录初步判断（未连接大模型）"}
      </div>
      {result.summary ? <p className="text-zinc-700">{result.summary}</p> : null}
      {useful.length ? (
        <ul className="space-y-1">
          {useful.map((s) => (
            <li key={s.key} className="flex gap-2">
              <span className="w-20 shrink-0 text-zinc-500">{byKey.get(s.key)?.label}</span>
              <span className={cn("shrink-0", STATUS[s.status].className)}>{STATUS[s.status].label}</span>
              <span className="min-w-0 text-zinc-600">{s.evidence}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-zinc-500">没有比当前记录更新的信息。</p>
      )}
      <div className="flex justify-end gap-2">
        <Button size="xs" variant="ghost" onClick={onClose}>
          忽略
        </Button>
        {editable && useful.length ? (
          <Button size="xs" disabled={save.isPending} onClick={apply}>
            采纳 {useful.length} 项
          </Button>
        ) : null}
      </div>
    </div>
  )
}

/** 商机侧栏：MEDDIC 赢单要素（完成度、风险、建议问题、AI 评估） */
export function MeddicCard({ oppId, editable }: { oppId: string; editable: boolean }) {
  const q = useMeddic(oppId)
  const assess = useAssessMeddic(oppId)
  const [result, setResult] = useState<MeddicAssessOut | null>(null)
  if (q.isPending) return <Skeleton className="h-40 w-full" />
  if (q.isError) return null
  const d = q.data
  return (
    <section aria-label="赢单要素" className="space-y-2 text-sm">
      <div className="flex h-7 items-center gap-2">
        <h3 className="text-zinc-500">赢单要素</h3>
        <span className="text-xs text-zinc-400">MEDDIC</span>
        <div className="ml-1 h-1.5 w-20 overflow-hidden rounded-full bg-zinc-100">
          <div
            className={cn("h-full", d.score >= 70 ? "bg-emerald-500" : d.score >= 40 ? "bg-amber-400" : "bg-zinc-400")}
            style={{ width: `${d.score}%` }}
          />
        </div>
        <span className="text-xs text-zinc-500 tabular-nums">{d.score}%</span>
        <Button
          size="xs"
          variant="outline"
          className="ml-auto"
          disabled={assess.isPending}
          onClick={() => assess.mutate(undefined, { onSuccess: setResult })}
        >
          {assess.isPending ? <Loader2 className="animate-spin" /> : <Sparkles className="text-ai" />}
          AI 评估
        </Button>
      </div>
      {d.risks.length ? (
        <div className="flex items-start gap-1.5 rounded-md bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800">
          <AlertTriangle className="mt-px size-3.5 shrink-0" />
          当前阶段还没确认：{d.risks.join("、")}。不影响推进阶段，但丢单风险较高。
        </div>
      ) : null}
      {result ? (
        <Assessment result={result} items={d.items} editable={editable} oppId={oppId} onClose={() => setResult(null)} />
      ) : null}
      <ul className="divide-y divide-zinc-100">
        {d.items.map((item) => (
          <Row key={`${item.key}-${item.updated_at ?? ""}`} item={item} editable={editable} oppId={oppId} />
        ))}
      </ul>
    </section>
  )
}
