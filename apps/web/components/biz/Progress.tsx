import { cn } from "@/lib/utils"

/** 回款进度条：w-24 细条 + 百分比；100% 绿色，其余蓝色（与原型 ContractGrid 一致） */
export function ProgressBar({ percent, className }: { percent: number; className?: string }) {
  // 条最多画满；数字写实际值（业绩完成率可以超过 100%）
  const actual = Math.max(0, Math.round(percent))
  const p = Math.min(100, actual)
  return (
    <span className={cn("inline-flex max-w-full min-w-0 items-center gap-2", className)}>
      <span
        className="h-1.5 w-24 min-w-6 shrink rounded-full bg-zinc-100"
        role="progressbar"
        aria-valuenow={p}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <span
          className={cn("block h-1.5 rounded-full", p >= 100 ? "bg-emerald-500" : "bg-blue-500")}
          style={{ width: `${p}%` }}
        />
      </span>
      <span className="shrink-0 text-zinc-500 tabular-nums">{actual}%</span>
    </span>
  )
}
