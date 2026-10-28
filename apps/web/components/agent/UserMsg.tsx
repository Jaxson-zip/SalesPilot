import { FileText } from "lucide-react"

import type { MaterialMeta } from "@/lib/agent-reducer"

/** 用户消息：右侧灰色气泡；附带材料时上方显示材料名（原文不回显） */
export function UserMsg({ text, material }: { text: string; material?: MaterialMeta | null }) {
  return (
    <div className="flex flex-col items-end gap-1.5">
      {material ? (
        <div className="inline-flex max-w-[80%] items-center gap-2 rounded-xl border border-zinc-200 bg-white px-3 py-2 text-xs">
          <FileText className="size-4 shrink-0 text-zinc-500" />
          <span className="truncate font-medium text-zinc-800">{material.name}</span>
          <span className="shrink-0 text-zinc-400">{material.chars.toLocaleString()} 字</span>
        </div>
      ) : null}
      <div className="max-w-[80%] rounded-2xl bg-zinc-100 px-4 py-2.5 text-[14px] leading-6 break-words whitespace-pre-wrap">
        {text}
      </div>
    </div>
  )
}
