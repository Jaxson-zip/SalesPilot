"use client"

import { Check, ChevronDown, Hand, RotateCcw, X } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import type { AgentStep, StepStatus } from "@/lib/agent-reducer"
import { cn } from "@/lib/utils"

/** 5 种状态图标：done 绿 / running 转圈 / retry 橙 / wait 紫 / error 红 */
export function StepIcon({ status }: { status: StepStatus }) {
  if (status === "running") {
    return (
      <span className="inline-flex size-5 items-center justify-center">
        <span className="size-3.5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
      </span>
    )
  }
  const map = {
    done: ["bg-emerald-50 text-emerald-600", Check],
    retry: ["bg-amber-50 text-amber-600", RotateCcw],
    wait: ["bg-violet-50 text-ai", Hand],
    error: ["bg-red-50 text-red-600", X],
  } as const
  const [tone, Icon] = map[status]
  return (
    <span className={cn("inline-flex size-5 items-center justify-center rounded-full", tone)}>
      <Icon className="size-3" />
    </span>
  )
}

function toJson(v: unknown): string {
  try {
    return typeof v === "string" ? v : JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

/** ThoughtChain 单步：点击展开工具的入参 / 出参；error 状态显示重试 */
export function ToolStep({ step, onRetry }: { step: AgentStep; onRetry?: () => void }) {
  const [open, setOpen] = useState(false)
  const hasDetail = step.args !== undefined || step.result !== undefined
  return (
    <div className="relative pb-3 pl-7 last:pb-0">
      <span className="absolute top-0 left-0">
        <StepIcon status={step.status} />
      </span>
      <button type="button" onClick={() => hasDetail && setOpen((o) => !o)} className="group w-full text-left">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-zinc-800">{step.title}</span>
          <code className="truncate font-mono text-[11px] text-zinc-400">{step.tool}</code>
          {hasDetail ? (
            <ChevronDown
              className={cn(
                "size-3 shrink-0 text-zinc-400 opacity-0 transition group-hover:opacity-100",
                open && "rotate-180 opacity-100",
              )}
            />
          ) : null}
        </div>
        <div
          className={cn(
            "mt-0.5 text-zinc-500",
            step.status === "retry" && "text-amber-700",
            step.status === "error" && "text-red-600",
          )}
        >
          {step.status === "running" ? "执行中…" : step.desc}
        </div>
      </button>
      {step.status === "error" && onRetry ? (
        <Button variant="outline" size="xs" className="mt-1.5 h-7" onClick={onRetry}>
          <RotateCcw />
          重试
        </Button>
      ) : null}
      {open ? (
        <pre className="mt-2 overflow-x-hidden rounded-md border border-zinc-100 bg-zinc-50 p-2.5 font-mono text-[11px] break-all whitespace-pre-wrap text-zinc-600">
          {step.args !== undefined ? `入参\n${toJson(step.args)}` : ""}
          {step.result !== undefined ? `\n\n出参\n${toJson(step.result)}` : ""}
        </pre>
      ) : null}
    </div>
  )
}
