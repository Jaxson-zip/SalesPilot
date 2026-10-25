import type { SourceRef } from "@/types/api"

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
        const cls =
          "inline-flex h-6 max-w-full items-center gap-1 rounded-md bg-zinc-100 px-2 text-zinc-600 hover:bg-zinc-200"
        return s.url ? (
          <a key={`${s.title}-${i}`} href={s.url} target="_blank" rel="noreferrer" className={cls}>
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
