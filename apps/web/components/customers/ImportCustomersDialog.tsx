"use client"

import { Download, FileUp } from "lucide-react"
import { useRef, useState } from "react"

import { Tag } from "@/components/biz/Tag"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useImportCustomers, usePreviewImport } from "@/hooks/useCustomers"
import { ACCEPT, fileProblem, importTemplate, previewSummary, rowsToShow, type ImportRow } from "@/lib/customer-import"
import { downloadText } from "@/lib/download"

function RowStatus({ row }: { row: ImportRow }) {
  if (row.status === "error") return <Tag color="red">有错误</Tag>
  if (row.status === "duplicate") return <Tag color="orange">重复</Tag>
  return <Tag color="blue">提示</Tag>
}

/**
 * 批量导入客户：下载模板 → 选文件 → 预览（逐行校验、查重）→「导入 N 个」。
 * 有问题的行跳过，不影响其他行；主管可以用「负责人」列分给本团队成员或放入公海。
 */
export function ImportCustomersDialog({
  open,
  onOpenChange,
  manager,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  manager: boolean
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const preview = usePreviewImport()
  const run = useImportCustomers()
  const result = preview.data
  const shown = result ? rowsToShow(result) : []

  const close = () => {
    setFile(null)
    setProblem(null)
    preview.reset()
    run.reset()
    onOpenChange(false)
  }
  const pick = (f: File) => {
    const why = fileProblem(f)
    setProblem(why)
    setFile(why ? null : f)
    preview.reset()
    if (!why) preview.mutate(f)
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? onOpenChange(true) : close())}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>批量导入客户</DialogTitle>
          <DialogDescription>
            支持 CSV 和 Excel（.xlsx），第一行是表头，只有「客户名称」必填，一次最多 1000 行。
            已存在的客户（按名称查重，忽略「有限公司」等后缀）会跳过。
            {manager ? "「负责人」列填本团队成员的姓名或账号，填「公海」放入本团队公海，留空归你自己。" : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => downloadText(importTemplate(manager), "客户导入模板.csv")}>
            <Download />
            下载模板
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPT}
            aria-label="选择要导入的文件"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              e.target.value = ""
              if (f) pick(f)
            }}
          />
          <Button size="sm" onClick={() => fileRef.current?.click()} disabled={preview.isPending || run.isPending}>
            <FileUp />
            {file ? "重新选择文件" : "选择文件"}
          </Button>
          {file ? <span className="truncate text-sm text-zinc-600">{file.name}</span> : null}
        </div>

        {problem ? <p className="text-sm text-red-600">{problem}</p> : null}
        {preview.isPending ? <p className="text-sm text-zinc-500">正在检查…</p> : null}

        {result ? (
          <section aria-label="导入预览" className="space-y-2">
            <p className="text-sm font-medium text-zinc-800">{previewSummary(result)}</p>
            {result.ignored_columns.length ? (
              <p className="text-xs text-zinc-500">没有识别的列（不会导入）：{result.ignored_columns.join("、")}</p>
            ) : null}
            {shown.length ? (
              <div className="max-h-72 overflow-auto rounded-md border border-zinc-200">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 bg-zinc-50 text-xs text-zinc-500">
                    <tr>
                      <th className="px-3 py-1.5 font-normal">行</th>
                      <th className="py-1.5 font-normal">客户名称</th>
                      <th className="py-1.5 font-normal">状态</th>
                      <th className="px-3 py-1.5 font-normal">说明</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((r) => (
                      <tr key={r.line} className="border-t border-zinc-100 align-top">
                        <td className="px-3 py-1.5 text-zinc-500 tabular-nums">{r.line}</td>
                        <td className="py-1.5 break-all">{r.name || "—"}</td>
                        <td className="py-1.5 whitespace-nowrap">
                          <RowStatus row={r} />
                        </td>
                        <td className="px-3 py-1.5 text-zinc-600">{r.message ?? r.warnings.join("；")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button
            disabled={!file || !result || result.ok === 0 || run.isPending}
            onClick={() => file && run.mutate(file, { onSuccess: close })}
          >
            {run.isPending ? "正在导入…" : result?.ok ? `导入 ${result.ok} 个客户` : "导入"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
