"use client"

import type { LucideIcon } from "lucide-react"

import { InfoPopover } from "@/components/biz/InfoPopover"
import { Skeleton } from "@/components/ui/skeleton"
import { useTemplates } from "@/hooks/useTemplates"
import type { RuleNoteKey } from "@/types/api"

/** 规则说明的悬浮卡片：比例、阈值都来自后端（rules.yaml），前端不写死数字 */
export function RuleHint({
  noteKey,
  label,
  icon,
  variant,
  align,
}: {
  noteKey: RuleNoteKey
  label?: string
  icon?: LucideIcon
  variant?: "button" | "link" | "icon"
  align?: "start" | "center" | "end"
}) {
  const q = useTemplates()
  const note = q.data?.rule_notes?.[noteKey]
  return (
    <InfoPopover
      label={label ?? note?.title ?? "规则说明"}
      title={note?.title}
      icon={icon}
      variant={variant}
      align={align}
    >
      {note ? (
        <div className="space-y-2.5">
          <dl className="space-y-1.5">
            {note.items.map((it) => (
              <div key={it.label} className="flex items-baseline justify-between gap-3">
                <dt className="shrink-0 text-zinc-500">{it.label}</dt>
                <dd className="text-right font-medium tabular-nums">{it.value}</dd>
              </div>
            ))}
          </dl>
          {note.note ? <p className="text-xs leading-5 text-zinc-600">{note.note}</p> : null}
          <p className="text-xs text-zinc-400">依据：{note.source}</p>
        </div>
      ) : q.isError ? (
        <p className="text-zinc-500">规则暂时读取失败，请稍后重试</p>
      ) : (
        <Skeleton className="h-20 w-full" />
      )}
    </InfoPopover>
  )
}
