import { cn } from "@/lib/utils"

/** 回款进度条：w-24 细条 + 百分比；100% 绿色，其余蓝色（与原型 ContractGrid 一致） */
export function ProgressBar({ percent, className }: { percent: number; className?: string }) {
  const p = Math.min(100, Math.max(0, Math.round(percent)))
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span
        className="h-1.5 w-24 shrink rounded-full bg-zinc-100"
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
      <span className="text-zinc-500 tabular-nums">{p}%</span>
    </span>
  )
}
