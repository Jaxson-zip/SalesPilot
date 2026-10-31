import type { SourceRef } from "@/types/api"
import { safeHref } from "@/lib/safe-url"

/** 参考来源（RAG 引用） */
export function Sources({ sources }: { sources: SourceRef[] }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <span className="text-zinc-400">参考来源</span>
      {sources.map((s, i) => {
        const inner = (
          <>
            <span className="inline-flex size-4 items-center justify-center rounded border border-zinc-200 bg-white text-[10px]">
              {i + 1}
            </span>
            <span className="truncate">{s.title}</span>
          </>
        )
        // 没有链接的来源只是标签，不给 hover 效果（避免看起来能点）
        const cls = "inline-flex h-6 max-w-full items-center gap-1 rounded-md bg-zinc-100 px-2 text-zinc-600"
        const href = safeHref(s.url)
        return href ? (
          <a
            key={`${s.title}-${i}`}
            href={href}
            target="_blank"
            rel="noreferrer"
            className={`${cls} hover:bg-zinc-200`}
          >
            {inner}
          </a>
        ) : (
          <span key={`${s.title}-${i}`} className={cls}>
            {inner}
          </span>
        )
      })}
    </div>
  )
}
