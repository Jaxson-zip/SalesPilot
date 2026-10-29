"use client"

import { BookOpen, FileText, Pencil, RotateCcw, Trash2, Upload } from "lucide-react"
import Link from "next/link"
import { useRef, useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { EmptyState } from "@/components/biz/EmptyState"
import { FormSheet } from "@/components/biz/FormSheet"
import { QueryError } from "@/components/biz/QueryStatus"
import { Tag } from "@/components/biz/Tag"
import { KnowledgeGuide } from "@/components/packs/KnowledgeGuide"
import { SettingsForm } from "@/components/settings/SettingsForm"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { usePackDetail } from "@/hooks/useProductLines"
import { useDeleteKnowledge, useSettings, useUpdateCatalogItem, useUploadKnowledge } from "@/hooks/useSettings"
import { formatFen } from "@/lib/format"
import { describeRules, formatBytes, specText, type PackCatalogItem, type PackDetail } from "@/lib/pack-rules"
import { CATEGORY_LABEL } from "@/lib/settings"

export type PackSection = "catalog" | "rules" | "knowledge"

export const PACK_SECTION_LABEL: Record<PackSection, string> = {
  catalog: "产品目录",
  rules: "业务规则",
  knowledge: "知识库",
}

const yuan = (fen: number) => String(Math.round(fen) / 100)

type Draft = Record<"name" | "unit" | "cost" | "price", string>

/** 一条产品：查看 / 原地编辑名称、单位、成本、售价（元）；改过的显示默认价并可恢复 */
function CatalogRow({ packId, it }: { packId: string; it: PackCatalogItem }) {
  const update = useUpdateCatalogItem(packId)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const category = CATEGORY_LABEL[it.category] ?? it.category
  const specs = specText(it.specs)

  if (draft) {
    const save = () => {
      const cost = Number(draft.cost)
      const price = Number(draft.price)
      if (!draft.name.trim() || !draft.unit.trim()) return setError("名称和单位不能为空")
      if (!draft.cost.trim() || !Number.isFinite(cost) || cost < 0) return setError("成本不能为负数")
      if (!Number.isFinite(price) || price <= 0) return setError("售价必须大于 0")
      update.mutate(
        {
          sku: it.sku,
          edit: {
            name: draft.name.trim(),
            unit: draft.unit.trim(),
            cost: Math.round(cost * 100),
            price: Math.round(price * 100),
          },
        },
        { onSuccess: () => setDraft(null) },
      )
    }
    const field = (k: keyof Draft, label: string, numeric = false) => (
      <label className="min-w-0 space-y-1">
        <span className="text-xs text-zinc-500">{label}</span>
        <Input
          value={draft[k]}
          aria-label={label}
          inputMode={numeric ? "decimal" : undefined}
          className={numeric ? "h-8 text-right" : "h-8"}
          onChange={(e) => setDraft((d) => (d ? { ...d, [k]: e.target.value } : d))}
        />
      </label>
    )
    return (
      <div className="space-y-2 bg-zinc-50/60 px-3 py-3">
        <div className="text-xs text-zinc-500">
          {it.sku} · {category}
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-[minmax(0,1fr)_72px_104px_104px]">
          <div className="col-span-2 sm:col-span-1">{field("name", "名称")}</div>
          {field("unit", "单位")}
          {field("cost", "成本（元）", true)}
          {field("price", "售价（元）", true)}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {error ? (
            <span role="alert" className="mr-auto text-xs text-red-600">
              {error}
            </span>
          ) : null}
          <Button variant="outline" size="xs" onClick={() => setDraft(null)} disabled={update.isPending}>
            取消
          </Button>
          <Button size="xs" onClick={save} disabled={update.isPending}>
            保存
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3 px-3 py-2.5">
      <div className="min-w-0 flex-1">
        <div className="font-medium break-words">{it.name}</div>
        <div className="mt-0.5 text-xs break-words text-zinc-400">
          {it.sku} · {category} · {it.unit}
          {specs ? ` · ${specs}` : ""}
        </div>
        {it.overridden ? (
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-zinc-500">
            <Tag color="yellow">已修改</Tag>
            <span>
              默认 成本 {formatFen(it.default_cost ?? it.cost)} · 售价 {formatFen(it.default_price ?? it.price)}
            </span>
            <button
              type="button"
              className="inline-flex items-center gap-0.5 text-zinc-600 hover:text-zinc-900 hover:underline"
              disabled={update.isPending}
              onClick={() => update.mutate({ sku: it.sku, edit: null })}
            >
              <RotateCcw className="size-3" />
              恢复默认
            </button>
          </div>
        ) : null}
      </div>
      <div className="shrink-0 text-right tabular-nums">
        <div className="font-medium">{formatFen(it.price)}</div>
        <div className="text-xs text-zinc-400">成本 {formatFen(it.cost)}</div>
      </div>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={`编辑 ${it.name}`}
        className="shrink-0"
        onClick={() => {
          setError(null)
          setDraft({ name: it.name, unit: it.unit, cost: yuan(it.cost), price: yuan(it.price) })
        }}
      >
        <Pencil />
      </Button>
    </div>
  )
}

function Catalog({ packId, items }: { packId: string; items: PackDetail["catalog"] }) {
  if (items.length === 0) return <EmptyState icon={FileText} title="产品目录为空" />
  return (
    <div className="space-y-2">
      <p className="text-xs text-zinc-500">
        改价后，新的方案和报价立即按新价格计算，已生成的报价单不变。增删物料需要配置器支持，仍由开发维护。
      </p>
      <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
        {items.map((it) => (
          <CatalogRow key={it.sku} packId={packId} it={it} />
        ))}
      </div>
    </div>
  )
}

/** 行业包参数（可改）+ 方案档位（与配置器逻辑绑定，只读） */
function Rules({ packId, rules }: { packId: string; rules: PackDetail["rules"] }) {
  const q = useSettings(packId)
  const pack = (rules.pack ?? {}) as Record<string, unknown>
  const fixed = describeRules({
    pack: {
      tiers: pack.tiers,
      tensor_parallel_sizes: pack.tensor_parallel_sizes,
      modules: pack.modules,
      custom_module: pack.custom_module,
    },
  })
  return (
    <div className="space-y-4">
      <p className="text-xs text-zinc-500">
        提成、报销、回款等通用规则在{" "}
        <Link href="/settings/rules" className="text-zinc-700 underline">
          系统设置 → 业务规则
        </Link>
        ，这里只放本行业的参数。
      </p>
      {q.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : q.isError ? (
        <QueryError error={q.error} onRetry={() => void q.refetch()} feature="行业包参数" />
      ) : (
        <SettingsForm packId={packId} data={q.data} />
      )}
      {fixed.length ? (
        <section aria-label="方案档位" className="rounded-lg border border-zinc-200">
          <div className="flex min-h-11 flex-wrap items-center justify-between gap-x-3 border-b border-zinc-100 px-4 py-2">
            <h3 className="font-medium">{pack.modules ? "方案档位与模块人天" : "方案档位"}</h3>
            <span className="text-xs text-zinc-400">与配置器选型逻辑绑定，由开发维护</span>
          </div>
          <dl className="divide-y divide-zinc-100">
            {fixed.map((r) => (
              <div key={r.key} className="grid gap-x-4 gap-y-1 px-4 py-2.5 sm:grid-cols-[200px_minmax(0,1fr)]">
                <dt className="text-zinc-600">{r.label}</dt>
                <dd className="min-w-0 break-words">{r.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
    </div>
  )
}

function Knowledge({ docs, packId }: { docs: PackDetail["knowledge"]; packId: string }) {
  const upload = useUploadKnowledge(packId)
  const remove = useDeleteKnowledge(packId)
  const { ask, dialog } = useConfirmAction()
  const fileRef = useRef<HTMLInputElement>(null)
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-zinc-500">{docs.filter((d) => d.indexed !== false).length} 份文档参与检索</span>
        <div className="flex items-center gap-2">
          <KnowledgeGuide packId={packId} />
          <input
            ref={fileRef}
            type="file"
            accept=".md,.pdf,.xlsx"
            aria-label="选择要上传的文档"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              e.target.value = ""
              if (f) upload.mutate(f)
            }}
          />
          <Button size="xs" onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
            <Upload />
            {upload.isPending ? "正在入库…" : "上传文档"}
          </Button>
        </div>
      </div>
      <p className="text-xs text-zinc-400">
        支持 Markdown、PDF、Excel，单个不超过 10 MB；上传后立即切块入库，AI 出方案和问答时就能引用。
      </p>
      {docs.length === 0 ? (
        <EmptyState icon={BookOpen} title="知识库还没有文档" />
      ) : (
        <ul aria-label="知识库文档" className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
          {docs.map((d) => (
            <li
              key={`${d.source ?? "builtin"}-${d.doc_name}`}
              aria-label={d.doc_name}
              className="flex items-center gap-2.5 px-3 py-2.5"
            >
              <span className="inline-flex h-5 w-11 shrink-0 items-center justify-center rounded bg-zinc-100 text-[11px] font-medium text-zinc-600 uppercase">
                {d.format ?? "file"}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium" title={d.title}>
                  {d.title || d.doc_name}
                </div>
                <div className="truncate text-xs text-zinc-400">
                  {d.source === "uploaded" ? "网页上传" : "内置"} · {d.doc_name} · {formatBytes(d.size)}
                </div>
              </div>
              {d.indexed === false ? (
                <span className="shrink-0 text-xs text-zinc-400" title="行业包的配置数据，不进入知识库检索">
                  配置数据 · 不入库
                </span>
              ) : typeof d.chunks === "number" ? (
                <span className="shrink-0 text-xs text-zinc-500 tabular-nums">
                  {d.chunks > 0 ? `已入库 ${d.chunks} 段` : "未入库"}
                </span>
              ) : null}
              {d.source === "uploaded" ? (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`删除 ${d.doc_name}`}
                  disabled={remove.isPending}
                  onClick={() =>
                    ask({
                      title: "删除文档",
                      description: `「${d.doc_name}」会从知识库里移除，AI 不再引用它。`,
                      confirmLabel: "确认删除",
                      destructive: true,
                      onConfirm: () => remove.mutate(d.doc_name),
                    })
                  }
                >
                  <Trash2 />
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {dialog}
    </div>
  )
}

/** 行业包内容：产品目录（可改价）/ 业务规则（可改本行业参数）/ 知识库（可上传）。文件里的是默认值 */
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
      wide
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
          {section === "catalog" ? <Catalog packId={q.data.id} items={q.data.catalog} /> : null}
          {section === "rules" ? <Rules packId={q.data.id} rules={q.data.rules} /> : null}
          {section === "knowledge" ? <Knowledge docs={q.data.knowledge} packId={q.data.id} /> : null}
        </>
      )}
    </FormSheet>
  )
}
