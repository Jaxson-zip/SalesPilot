"use client"

import { Upload } from "lucide-react"
import { useRef, useState, type DragEvent } from "react"
import { toast } from "sonner"

import { AttachmentItem } from "@/components/biz/Attachments"
import { SimpleSelect } from "@/components/biz/FormControls"
import { UploadGuide } from "@/components/expenses/UploadGuide"
import { useDeleteAttachment, useUploadAttachment } from "@/hooks/useExpenses"
import { attachmentSummary, validateAttachmentFile } from "@/lib/expense"
import { ATTACHMENT_KIND_META } from "@/lib/labels"
import { cn } from "@/lib/utils"
import type { AttachmentKind, AttachmentOut, ExpenseType } from "@/types/api"

const KIND_OPTIONS: { value: AttachmentKind; label: string }[] = (["invoice", "receipt", "other"] as const).map(
  (k) => ({ value: k, label: ATTACHMENT_KIND_META[k].label }),
)

/**
 * Uploader：票据类型 + 拖拽 / 点击上传区 + 已上传文件列表（multipart：file + kind）。
 * 还没有草稿时（U5）：选择文件后先调用 ensureDraft 自动保存草稿，拿到 id 再上传；表单不完整时 ensureDraft 返回 null。
 */
export function AttachmentUploader({
  expenseId,
  type,
  attachments,
  editable,
  ensureDraft,
}: {
  expenseId: string | null
  /** 费用类型：决定格式说明里「本类需要」哪些票据 */
  type: ExpenseType
  attachments: AttachmentOut[]
  editable: boolean
  /** 没有草稿时自动保存草稿，返回报销单 id；表单校验不通过返回 null */
  ensureDraft?: () => Promise<string | null>
}) {
  const [kind, setKind] = useState<AttachmentKind>("invoice")
  const [dragging, setDragging] = useState(false)
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const upload = useUploadAttachment()
  const remove = useDeleteAttachment()
  const busy = upload.isPending || saving
  const disabled = !editable || busy || (!expenseId && !ensureDraft)

  const handleFiles = async (files: FileList | null) => {
    if (!files || disabled) return
    const list = Array.from(files).filter((file) => {
      const err = validateAttachmentFile(file)
      if (err) toast.error(err)
      return !err
    })
    if (list.length === 0) return
    let id = expenseId
    if (!id && ensureDraft) {
      setSaving(true)
      try {
        id = await ensureDraft()
      } finally {
        setSaving(false)
      }
    }
    if (!id) return
    for (const file of list) {
      upload.mutate({ expenseId: id, file, kind }, { onSuccess: () => toast.success(`已上传 ${file.name}`) })
    }
  }
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(false)
    void handleFiles(e.dataTransfer.files)
  }

  return (
    <div className="space-y-2">
      {editable ? (
        <div className="flex items-center gap-2">
          <span className="shrink-0 text-zinc-500">本次上传为</span>
          <div className="w-28">
            <SimpleSelect value={kind} onChange={setKind} options={KIND_OPTIONS} size="sm" ariaLabel="票据类型" />
          </div>
          <span className="ml-auto">
            <UploadGuide type={type} />
          </span>
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
            "focus-visible:ring-ring/50 flex items-center gap-3 rounded-md border border-dashed px-4 py-4 outline-none focus-visible:ring-2",
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
              {saving ? "正在保存草稿…" : upload.isPending ? "上传中…" : "点击或拖拽文件到这里上传"}
            </div>
            <div className="text-xs text-zinc-500">
              {expenseId ? attachmentSummary(attachments) : "选择文件后会自动保存草稿再上传"}
            </div>
          </div>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
            className="hidden"
            onChange={(e) => {
              // handleFiles 在第一个 await 之前已同步复制了文件列表，可以立即清空
              void handleFiles(e.target.files)
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
        {!editable && attachments.length === 0 ? <div className="text-zinc-500">没有票据</div> : null}
        {attachments.length > 0 ? (
          <p className="text-xs text-zinc-500">
            已上传 ≠ 已验真：系统只检查文件格式和票据类型，不核验发票真伪；主管审批时会逐张核对。
          </p>
        ) : null}
      </div>
    </div>
  )
}
