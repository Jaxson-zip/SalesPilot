"use client"

import { BookOpen, FileText } from "lucide-react"

import { EmptyState } from "@/components/biz/EmptyState"
import { FormSheet } from "@/components/biz/FormSheet"
import { QueryError } from "@/components/biz/QueryStatus"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { usePackDetail } from "@/hooks/useProductLines"
import { formatFen } from "@/lib/format"
import { describeRules, formatBytes, specText, type PackDetail } from "@/lib/pack-rules"

export type PackSection = "catalog" | "rules" | "knowledge"

export const PACK_SECTION_LABEL: Record<PackSection, string> = {
  catalog: "产品目录",
  rules: "业务规则",
  knowledge: "知识库",
}

/** 产品目录：≥640 表格；<640 卡片（不横向滚动）。价格按元显示 */
function Catalog({ items }: { items: PackDetail["catalog"] }) {
  if (items.length === 0) return <EmptyState icon={FileText} title="产品目录为空" />
  return (
    <div className="overflow-hidden rounded-lg border border-zinc-200">
      <table className="hidden w-full table-fixed sm:table">
        <thead>
          <tr className="h-8 bg-zinc-50 text-zinc-500">
            <th className="px-3 text-left font-normal">产品</th>
            <th className="w-16 px-2 text-left font-normal">类别</th>
            <th className="w-[84px] px-2 text-right font-normal">成本</th>
            <th className="w-[84px] px-3 text-right font-normal">售价</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.sku} className="border-t border-zinc-100 align-top">
              <td className="px-3 py-2">
                <div className="truncate font-medium" title={it.name}>
                  {it.name}
                </div>
                <div className="truncate text-xs text-zinc-400" title={specText(it.specs)}>
                  {it.sku} · {it.unit}
                </div>
              </td>
              <td className="truncate px-2 py-2 text-zinc-600">{it.category}</td>
              <td className="px-2 py-2 text-right text-zinc-500 tabular-nums">{formatFen(it.cost)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatFen(it.price)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="divide-y divide-zinc-100 sm:hidden">
        {items.map((it) => (
          <div key={it.sku} className="space-y-1 px-3 py-2.5">
            <div className="flex items-start justify-between gap-3">
              <span className="min-w-0 font-medium break-words">{it.name}</span>
              <span className="shrink-0 font-medium tabular-nums">{formatFen(it.price)}</span>
            </div>
            <div className="text-xs text-zinc-500">
              {it.sku} · {it.category} · {it.unit} · 成本 {formatFen(it.cost)}
            </div>
            {specText(it.specs) ? <div className="text-xs break-words text-zinc-400">{specText(it.specs)}</div> : null}
          </div>
        ))}
      </div>
    </div>
  )
}

function Rules({ rules }: { rules: PackDetail["rules"] }) {
  const rows = describeRules(rules)
  if (rows.length === 0) return <EmptyState icon={FileText} title="该行业包没有覆盖通用规则" />
  return (
    <dl className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
      {rows.map((r) => (
        <div key={r.key} className="flex flex-col gap-0.5 px-3 py-2.5 sm:flex-row sm:gap-3">
          <dt className="shrink-0 text-zinc-500 sm:w-44" title={r.key}>
            {r.label}
          </dt>
          <dd className="min-w-0 break-words tabular-nums">{r.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Knowledge({ docs }: { docs: PackDetail["knowledge"] }) {
  if (docs.length === 0) return <EmptyState icon={BookOpen} title="知识库还没有文档" />
  return (
    <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
      {docs.map((d) => (
        <div key={d.doc_name} className="flex items-center gap-2.5 px-3 py-2.5">
          <FileText className="size-4 shrink-0 text-zinc-400" />
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium" title={d.title}>
              {d.title || d.doc_name}
            </div>
            <div className="truncate text-xs text-zinc-400">{d.doc_name}</div>
          </div>
          <span className="shrink-0 text-xs text-zinc-500 tabular-nums">{formatBytes(d.size)}</span>
        </div>
      ))}
    </div>
  )
}

/** 行业包内容（只读）：产品目录 / 业务规则 / 知识库。内容在 core 的 packs/<id>/ 目录维护 */
export function PackDetailSheet({
  packId,
  packName,
  section,
  onClose,
}: {
  packId: string | null
  packName: string
  section: PackSection
  onClose: () => void
}) {
  const q = usePackDetail(packId)
  return (
    <FormSheet
      open={packId !== null}
      onOpenChange={(o) => !o && onClose()}
      title={`${packName} · ${PACK_SECTION_LABEL[section]}`}
      footer={
        <Button variant="outline" onClick={onClose}>
          关闭
        </Button>
      }
    >
      {q.isPending ? (
        <Skeleton className="h-48 w-full" />
      ) : q.isError ? (
        <QueryError error={q.error} onRetry={() => void q.refetch()} retrying={q.isFetching} feature="行业包详情" />
      ) : (
        <>
          <p className="text-xs text-zinc-500">
            只读 · v{q.data.version} · 内容在 packs/{q.data.id}/ 目录维护
          </p>
          {section === "catalog" ? <Catalog items={q.data.catalog} /> : null}
          {section === "rules" ? <Rules rules={q.data.rules} /> : null}
          {section === "knowledge" ? <Knowledge docs={q.data.knowledge} /> : null}
        </>
      )}
    </FormSheet>
  )
}
