"use client"

import { TriangleAlert } from "lucide-react"
import type { ReactNode } from "react"

import { Tag } from "@/components/biz/Tag"
import type { ModelCard } from "@/hooks/useModelConfig"
import { KIND_LABELS } from "@/lib/model-config"

export function time(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 可用 / 不可用 / 未配置 / 状态未知（网关连不上） */
export function AvailTag({ available, configured = true }: { available: boolean | null; configured?: boolean }) {
  if (!configured) return <Tag>未配置</Tag>
  if (available === null) return <Tag>状态未知</Tag>
  return available ? <Tag color="green">可用</Tag> : <Tag color="yellow">不可用</Tag>
}

/** 一个模型的小标签：别名 + 用途 + 是否可用 */
export function ModelChip({ m }: { m: Pick<ModelCard, "alias" | "kind" | "available"> & { tools?: boolean } }) {
  return (
    <span
      className={
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs " +
        (m.available ? "border-zinc-200 text-zinc-600" : "border-dashed border-zinc-300 text-zinc-400")
      }
    >
      {m.alias}
      <span className="text-zinc-400">
        {KIND_LABELS[m.kind]}
        {m.kind === "chat" && m.tools === false ? "·不支持工具" : ""}
      </span>
    </span>
  )
}

export function Warn({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-1.5 text-xs text-red-600">
      <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
      <span>{children}</span>
    </p>
  )
}

export function Section({ title, desc, children }: { title: string; desc?: ReactNode; children: ReactNode }) {
  return (
    <section aria-label={title} className="space-y-3">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        {desc ? <div className="mt-0.5 text-xs text-zinc-500">{desc}</div> : null}
      </div>
      {children}
    </section>
  )
}
