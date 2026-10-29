"use client"

import { AlertTriangle, Copy, Download, FileText, Loader2, RefreshCw } from "lucide-react"
import { toast } from "sonner"

import { ChatMarkdown } from "@/components/agent/ChatMarkdown"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { useGeneratePrd, usePrd } from "@/hooks/usePrd"
import { downloadText } from "@/lib/download"
import { formatRelative } from "@/lib/format"
import { prdFileName } from "@/lib/prd"

/**
 * PRD 规格书：按商机的需求清单生成（软件外包），Markdown 预览、复制（可直接粘到飞书 / 钉钉 / Notion）、下载 .md。
 * 负责人可以生成 / 重新生成；其他能看到商机的人只读。
 */
export function PrdDialog({
  oppId,
  title,
  canGenerate,
  open,
  onOpenChange,
}: {
  oppId: string
  title: string
  canGenerate: boolean
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const query = usePrd(oppId, open)
  const gen = useGeneratePrd(oppId)
  const prd = query.data
  const text = gen.running ? gen.draft : (prd?.markdown ?? "")

  const copy = () =>
    navigator.clipboard
      .writeText(text)
      .then(() => toast.success("已复制 Markdown，可直接粘贴到飞书 / 钉钉 / Notion 文档"))
      .catch(() => toast.error("复制失败"))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90dvh] flex-col gap-3 sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="size-4" />
            PRD 规格书
          </DialogTitle>
          <DialogDescription>
            {gen.running
              ? "AI 正在按需求清单撰写，约 30–60 秒…"
              : prd
                ? `${prd.source === "ai" ? "AI 扩写" : "模板版"} · ${prd.generated_by} ${formatRelative(prd.generated_at)}生成 · 需求${prd.confirmed ? "已确认" : "未确认"}`
                : "按需求清单生成项目背景、范围、角色权限、模块用例、数据结构、非功能需求和验收标准"}
          </DialogDescription>
        </DialogHeader>

        {prd?.stale && !gen.running ? (
          <p className="flex items-start gap-1.5 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <AlertTriangle className="mt-px size-3.5 shrink-0" />
            需求清单在生成之后改过，PRD 可能不是最新的{canGenerate ? "，建议重新生成" : ""}。
          </p>
        ) : null}

        <div className="min-h-40 flex-1 overflow-y-auto rounded-lg border border-zinc-200 px-4 py-3">
          {query.isPending && !gen.running ? (
            <Skeleton className="h-40 w-full" />
          ) : text ? (
            <div className="prose-chat text-sm break-words" aria-label="PRD 预览">
              <ChatMarkdown text={text} />
            </div>
          ) : gen.running ? (
            <div className="flex h-40 items-center justify-center gap-2 text-sm text-zinc-500">
              <Loader2 className="size-4 animate-spin" />
              正在生成…
            </div>
          ) : (
            <div className="flex h-40 flex-col items-center justify-center gap-1 text-center text-sm text-zinc-500">
              还没有生成 PRD
              {canGenerate ? null : <span className="text-xs">由商机负责人生成</span>}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          {canGenerate ? (
            <Button
              variant={prd ? "outline" : "default"}
              size="sm"
              disabled={gen.running}
              onClick={() => void gen.generate()}
            >
              {gen.running ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              {prd ? "重新生成" : "生成 PRD"}
            </Button>
          ) : null}
          <Button variant="outline" size="sm" disabled={!prd || gen.running} onClick={copy}>
            <Copy />
            复制 Markdown
          </Button>
          <Button
            size="sm"
            disabled={!prd || gen.running}
            onClick={() => prd && downloadText(prd.markdown, prdFileName(title), "text/markdown;charset=utf-8")}
          >
            <Download />
            下载 .md
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
