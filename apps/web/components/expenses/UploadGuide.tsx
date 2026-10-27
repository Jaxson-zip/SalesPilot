"use client"

import { Download, Eye, FileQuestion } from "lucide-react"

import { InfoPopover } from "@/components/biz/InfoPopover"
import { useTemplates } from "@/hooks/useTemplates"
import { MAX_ATTACHMENT_BYTES, formatBytes } from "@/lib/expense"
import type { ExpenseType } from "@/types/api"

/** 样例文件（带「样例 · 非真实票据」水印，生成脚本：scripts/samples/build.mjs） */
export const RECEIPT_SAMPLES = [
  {
    key: "invoice",
    label: "电子发票样例",
    preview: "/samples/invoice-sample.png",
    download: "/samples/invoice-sample.pdf",
    fileName: "电子发票样例.pdf",
  },
  {
    key: "receipt",
    label: "消费小票样例",
    preview: "/samples/receipt-sample.png",
    download: "/samples/receipt-sample.png",
    fileName: "消费小票样例.png",
  },
] as const

const PHOTO_RULES = [
  "电子发票直接上传 PDF 原件，不要截图",
  "纸质票据拍照：四角完整、文字清晰、不反光",
  "发票抬头为公司全称，税号与公司一致",
  "金额、日期与报销单填写的一致",
]

function SampleCard({ sample }: { sample: (typeof RECEIPT_SAMPLES)[number] }) {
  return (
    <figure className="min-w-0 overflow-hidden rounded-md border border-zinc-200">
      <a href={sample.preview} target="_blank" rel="noreferrer" title={`查看${sample.label}`}>
        {/* eslint-disable-next-line @next/next/no-img-element -- 静态样例图，不需要图片优化 */}
        <img src={sample.preview} alt={sample.label} className="h-24 w-full bg-zinc-50 object-contain" />
      </a>
      <figcaption className="flex items-center justify-between gap-1 border-t border-zinc-100 px-2 py-1.5 text-xs">
        <span className="truncate text-zinc-600">{sample.label}</span>
        <span className="flex shrink-0 gap-1.5">
          <a href={sample.preview} target="_blank" rel="noreferrer" aria-label={`查看${sample.label}`}>
            <Eye className="size-3.5 text-zinc-500 hover:text-zinc-900" />
          </a>
          <a href={sample.download} download={sample.fileName} aria-label={`下载${sample.label}`}>
            <Download className="size-3.5 text-zinc-500 hover:text-zinc-900" />
          </a>
        </span>
      </figcaption>
    </figure>
  )
}

/** 上传区的「格式说明与样例」悬浮卡片：格式与大小、当前类型需要哪些票据、拍照要求、样例预览和下载 */
export function UploadGuide({ type }: { type: ExpenseType }) {
  const guide = useTemplates().data?.expense_guides.find((g) => g.type === type)
  return (
    <InfoPopover label="格式说明与样例" title="票据格式说明" icon={FileQuestion} variant="link" className="w-96">
      <div className="space-y-3 text-[13px]">
        <dl className="space-y-1.5">
          <div className="flex gap-3">
            <dt className="w-16 shrink-0 text-zinc-500">文件格式</dt>
            <dd>JPG / PNG / PDF，单个不超过 {formatBytes(MAX_ATTACHMENT_BYTES)}</dd>
          </div>
          {guide ? (
            <div className="flex gap-3">
              <dt className="w-16 shrink-0 text-zinc-500">本类需要</dt>
              <dd>
                {guide.attachments.join(" + ")}（{guide.label}）
              </dd>
            </div>
          ) : null}
        </dl>
        <ul className="list-disc space-y-0.5 pl-4 text-zinc-600">
          {PHOTO_RULES.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        <div className="grid grid-cols-2 gap-2">
          {RECEIPT_SAMPLES.map((s) => (
            <SampleCard key={s.key} sample={s} />
          ))}
        </div>
        <p className="text-xs text-zinc-400">样例带水印，仅用于说明需要看清哪些信息</p>
      </div>
    </InfoPopover>
  )
}
