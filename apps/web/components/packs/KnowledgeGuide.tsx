"use client"

import { Download, FileQuestion } from "lucide-react"

import { InfoPopover } from "@/components/biz/InfoPopover"

/** 知识库支持的格式、处理方式和样例文件（与 core app/rag/loaders.py 一致） */
export const KNOWLEDGE_FORMATS = [
  {
    format: "md",
    label: "Markdown",
    how: "按 # / ## / ### 标题拆成小节，出处显示到章节",
    sample: { href: "/samples/kb-sample.md", name: "知识文档样例.md" },
  },
  {
    format: "pdf",
    label: "PDF",
    how: "按页提取，自动去掉页眉页码，识别「第 X 章」「2.1」标题，出处显示到页",
    sample: { href: "/samples/kb-sample.pdf", name: "知识文档样例.pdf" },
  },
  {
    format: "xlsx",
    label: "Excel",
    how: "每张工作表转成一张表格（第一行作表头），长表格按行切开并重复表头",
    sample: { href: "/samples/kb-sample.xlsx", name: "参数表样例.xlsx" },
  },
] as const

export function KnowledgeGuide({ packId }: { packId: string }) {
  return (
    <InfoPopover
      label="支持的格式与样例"
      title="知识库文档格式"
      icon={FileQuestion}
      variant="link"
      className="w-96"
      align="end"
    >
      <div className="space-y-3 text-[13px]">
        <ul className="space-y-2">
          {KNOWLEDGE_FORMATS.map((f) => (
            <li key={f.format} className="flex gap-2.5">
              <span className="mt-0.5 inline-flex h-5 w-12 shrink-0 items-center justify-center rounded bg-zinc-100 text-[11px] font-medium text-zinc-600 uppercase">
                {f.format}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-zinc-700">{f.how}</div>
                <a
                  href={f.sample.href}
                  download={f.sample.name}
                  className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-900"
                >
                  <Download className="size-3" />
                  下载{f.label}样例
                </a>
              </div>
            </li>
          ))}
        </ul>
        <div className="rounded-md bg-zinc-50 px-3 py-2 text-xs leading-5 text-zinc-600">
          添加方式：把文件放到 <code className="text-zinc-800">packs/{packId}/knowledge/</code>，再执行
          <code className="ml-1 text-zinc-800">python -m app.rag.ingest --scope pack:{packId}</code>
          。价格不要写进知识库，统一维护在产品目录。
        </div>
      </div>
    </InfoPopover>
  )
}
