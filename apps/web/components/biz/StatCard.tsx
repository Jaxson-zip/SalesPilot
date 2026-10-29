import type { LucideIcon } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"

/** 工作台指标卡（StatCard），≥1280 一行 4 个，更窄 2 个（由父级 grid 决定） */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  loading,
}: {
  label: string
  value: string
  hint?: string
  icon: LucideIcon
  loading?: boolean
}) {
  return (
    <div className="min-w-0 rounded-lg border border-zinc-200 p-4">
      <div className="flex items-center justify-between text-zinc-500">
        <span className="truncate">{label}</span>
        <Icon className="size-4 shrink-0 text-zinc-400" />
      </div>
      {loading ? (
        <Skeleton className="mt-2.5 h-6 w-24" />
      ) : (
        <div className="mt-1.5 truncate text-[22px] font-semibold tabular-nums">{value}</div>
      )}
      {hint ? <div className="text-xs text-zinc-500 max-sm:line-clamp-2 sm:truncate">{hint}</div> : null}
    </div>
  )
}
