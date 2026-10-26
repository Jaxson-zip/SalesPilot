"use client"

import { Upload } from "lucide-react"
import { useRef, useState, type DragEvent } from "react"
import { toast } from "sonner"

import { AttachmentItem } from "@/components/biz/Attachments"
import { SimpleSelect } from "@/components/biz/FormControls"
import { useDeleteAttachment, useUploadAttachment } from "@/hooks/useExpenses"
import { attachmentSummary, validateAttachmentFile } from "@/lib/expense"
import { ATTACHMENT_KIND_META } from "@/lib/labels"
import { cn } from "@/lib/utils"
import type { AttachmentKind, AttachmentOut } from "@/types/api"

const KIND_OPTIONS: { value: AttachmentKind; label: string }[] = (["invoice", "receipt", "other"] as const).map(
  (k) => ({ value: k, label: ATTACHMENT_KIND_META[k].label }),
)

/**
 * Uploader：票据类型 + 拖拽 / 点击上传区 + 已上传文件列表。
 * 必须先保存草稿拿到报销单 id 才能上传（multipart：file + kind）。
 */
export function AttachmentUploader({
  expenseId,
  attachments,
  editable,
}: {
  expenseId: string | null
  attachments: AttachmentOut[]
  editable: boolean
}) {
  const [kind, setKind] = useState<AttachmentKind>("invoice")
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const upload = useUploadAttachment(expenseId)
  const remove = useDeleteAttachment()
  const disabled = !expenseId || !editable || upload.isPending

  const handleFiles = (files: FileList | null) => {
    if (!files || disabled) return
    for (const file of Array.from(files)) {
      const err = validateAttachmentFile(file)
      if (err) {
        toast.error(err)
        continue
      }
      upload.mutate({ file, kind }, { onSuccess: () => toast.success(`已上传 ${file.name}`) })
    }
  }
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div className="space-y-2">
      {editable ? (
        <div className="flex items-center gap-2">
          <span className="shrink-0 text-zinc-500">本次上传为</span>
          <div className="w-28">
            <SimpleSelect value={kind} onChange={setKind} options={KIND_OPTIONS} size="sm" ariaLabel="票据类型" />
          </div>
        </div>
      ) : null}
      {editable ? (
        <div
          role="button"
          tabIndex={0}
          aria-disabled={disabled}
          onClick={() => !disabled && inputRef.current?.click()}
          onKeyDown={(e) => e.key === "Enter" && !disabled && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            if (!disabled) setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "flex items-center gap-3 rounded-md border border-dashed px-4 py-4 outline-none",
            disabled
              ? "cursor-not-allowed border-zinc-200 opacity-60"
              : "cursor-pointer border-zinc-300 hover:bg-zinc-50",
            dragging && "border-zinc-500 bg-zinc-50",
          )}
        >
          <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-zinc-100">
            <Upload className="size-4 text-zinc-500" />
          </span>
          <div className="min-w-0">
            <div className="font-medium">
              {!expenseId ? "保存草稿后即可上传票据" : upload.isPending ? "上传中…" : "点击或拖拽文件到这里上传"}
            </div>
            <div className="text-xs text-zinc-500">{attachmentSummary(attachments)}</div>
          </div>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
            className="hidden"
            onChange={(e) => {
              handleFiles(e.target.files)
              e.target.value = ""
            }}
          />
        </div>
      ) : null}
      <div className="space-y-1.5">
        {attachments.map((a) => (
          <AttachmentItem
            key={a.id}
            a={a}
            deleting={remove.isPending && remove.variables === a.id}
            onDelete={editable ? () => remove.mutate(a.id) : undefined}
          />
        ))}
        {!editable && attachments.length === 0 ? <div className="text-zinc-400">没有票据</div> : null}
      </div>
    </div>
  )
}
