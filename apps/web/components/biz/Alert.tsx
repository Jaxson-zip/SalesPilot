import { CircleCheck, Info, Sparkles, TriangleAlert, type LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

/** 原型 Alert：warn 超标 / info 说明 / ai AI 建议 / ok 校验通过 */
const TONES: Record<"warn" | "info" | "ai" | "ok", { cls: string; icon: LucideIcon }> = {
  warn: { cls: "border-amber-200 bg-amber-50 text-amber-900", icon: TriangleAlert },
  info: { cls: "border-zinc-200 bg-white text-zinc-800", icon: Info },
  ai: { cls: "border-violet-200 bg-violet-50 text-violet-900", icon: Sparkles },
  ok: { cls: "border-emerald-200 bg-emerald-50 text-emerald-900", icon: CircleCheck },
}

export type AlertTone = keyof typeof TONES

export function Alert({
  tone,
  title,
  children,
  className,
}: {
  tone: AlertTone
  title: string
  children?: ReactNode
  className?: string
}) {
  const t = TONES[tone]
  return (
    <div className={cn("flex gap-2.5 rounded-lg border px-3.5 py-3", t.cls, className)} role="status">
      <t.icon className={cn("mt-0.5 size-4 shrink-0", tone === "ai" && "text-ai")} />
      <div className="min-w-0">
        <div className="font-medium">{title}</div>
        {children ? <div className="mt-0.5 opacity-80">{children}</div> : null}
      </div>
    </div>
  )
}
