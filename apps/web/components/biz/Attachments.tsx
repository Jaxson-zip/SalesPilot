"use client"

import { Eye, FileText, Image as ImageIcon, X } from "lucide-react"
import { toast } from "sonner"

import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import { fetchBlobUrl } from "@/lib/api"
import { errorMessage } from "@/lib/errors"
import { formatBytes } from "@/lib/expense"
import { ATTACHMENT_KIND_META } from "@/lib/labels"
import { cn } from "@/lib/utils"
import type { AttachmentOut } from "@/types/api"

function isImage(a: Pick<AttachmentOut, "mime" | "file_name">): boolean {
  return a.mime.startsWith("image/") || /\.(png|jpe?g)$/i.test(a.file_name)
}

/** 带鉴权地打开附件（GET /api/attachments/{id}/file 需要登录，登录 Cookie 由浏览器自动带上） */
export async function openAttachment(a: AttachmentOut): Promise<void> {
  // 先同步打开窗口，避免异步之后被浏览器拦截弹窗
  const win = window.open("", "_blank")
  try {
    const url = await fetchBlobUrl(a.url || `/api/attachments/${a.id}/file`)
    if (win) win.location.href = url
    else window.location.assign(url)
  } catch (err) {
    win?.close()
    toast.error(`无法打开附件：${errorMessage(err)}`)
  }
}

function FileIcon({ a }: { a: AttachmentOut }) {
  const img = isImage(a)
  return (
    <span
      className={cn(
        "inline-flex size-8 shrink-0 items-center justify-center rounded-md",
        img ? "bg-sky-50 text-sky-600" : "bg-red-50 text-red-500",
      )}
    >
      {img ? <ImageIcon className="size-4" /> : <FileText className="size-4" />}
    </span>
  )
}

/** 已上传文件行：类型标记、预览、删除（仅草稿可删除） */
export function AttachmentItem({
  a,
  onDelete,
  deleting,
}: {
  a: AttachmentOut
  onDelete?: () => void
  deleting?: boolean
}) {
  const kind = ATTACHMENT_KIND_META[a.kind] ?? ATTACHMENT_KIND_META.other
  return (
    <div className="flex h-12 min-w-0 items-center gap-2.5 rounded-md border border-zinc-200 bg-white px-2.5">
      <FileIcon a={a} />
      <div className="min-w-0 flex-1">
        <div className="truncate" title={a.file_name}>
          {a.file_name}
        </div>
        <div className="text-[11px] text-zinc-400">{formatBytes(a.size)}</div>
      </div>
      <Tag color={kind.color}>{kind.label}</Tag>
      <Button variant="ghost" size="icon-xs" className="size-7" title="预览" onClick={() => void openAttachment(a)}>
        <Eye />
      </Button>
      {onDelete ? (
        <Button variant="ghost" size="icon-xs" className="size-7" title="删除" disabled={deleting} onClick={onDelete}>
          <X />
        </Button>
      ) : null}
    </div>
  )
}

/** 审批列表里的附件按钮（紧凑） */
export function AttachmentPill({ a }: { a: AttachmentOut }) {
  const img = isImage(a)
  return (
    <button
      type="button"
      onClick={() => void openAttachment(a)}
      className="inline-flex h-7 max-w-full min-w-0 items-center gap-1.5 rounded-md border border-zinc-200 px-2 hover:bg-zinc-50"
      title={a.file_name}
    >
      {img ? (
        <ImageIcon className="size-3.5 shrink-0 text-sky-600" />
      ) : (
        <FileText className="size-3.5 shrink-0 text-red-500" />
      )}
      <span className="truncate">{a.file_name}</span>
    </button>
  )
}
