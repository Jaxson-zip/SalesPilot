"use client"

import { CircleAlert, CircleCheck, Loader2 } from "lucide-react"

import type { ModelConfig } from "@/hooks/useModelConfig"
import { aiStatus } from "@/lib/model-config"
import { cn } from "@/lib/utils"

/** 页面顶部：AI 现在能不能用，对话 / 知识库 / 重排各自在用谁 */
export function StatusSummary({ config }: { config: ModelConfig }) {
  const lines = aiStatus(config)
  const chatReady = lines[0].value !== null
  const job = config.reindex
  return (
    <section
      aria-label="当前状态"
      className={cn(
        "rounded-lg border p-4",
        chatReady ? "border-emerald-200 bg-emerald-50/50" : "border-amber-200 bg-amber-50",
      )}
    >
      <p className="flex items-center gap-2 font-medium">
        {chatReady ? (
          <CircleCheck className="size-4 text-emerald-600" />
        ) : (
          <CircleAlert className="size-4 text-amber-600" />
        )}
        {!config.gateway_ok ? "模型服务连不上" : chatReady ? "AI 可以正常使用" : "AI 还不能用：至少填一家的 Key"}
      </p>
      {config.gateway_ok ? (
        <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
          {lines.map((l) => (
            <div key={l.label} className="flex gap-2">
              <dt className="shrink-0 text-zinc-500">{l.label}</dt>
              <dd className={l.value ? "" : "text-zinc-400"}>
                {l.value ?? (l.label === "重排" ? "不使用" : "不可用")}
                {l.backups.length ? <span className="text-zinc-400"> · 备用 {l.backups.join("、")}</span> : null}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="mt-1 text-sm text-zinc-600">这里保存的 Key 会在恢复后自动生效。</p>
      )}
      {job.status === "running" ? (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-zinc-600">
          <Loader2 className="size-3.5 animate-spin" />
          知识库正在换到 {job.target}：{job.done} / {job.total}
        </p>
      ) : null}
    </section>
  )
}
