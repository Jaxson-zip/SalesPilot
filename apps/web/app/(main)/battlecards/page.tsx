"use client"

import { ChevronRight, Pencil, Plus, Search, Swords, Trash2 } from "lucide-react"
import { useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { EmptyState } from "@/components/biz/EmptyState"
import { PageFrame } from "@/components/biz/PageFrame"
import { QueryError } from "@/components/biz/QueryStatus"
import { BattleCardBody, CompetitorRecord } from "@/components/competitors/BattleCard"
import { CompetitorForm } from "@/components/competitors/CompetitorForm"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useDebounced } from "@/hooks/useDebounced"
import { useCompetitors, useDeleteCompetitor, type Competitor } from "@/hooks/useCompetitors"
import { deleteCompetitorConfirm } from "@/lib/confirm-texts"
import { cn } from "@/lib/utils"

/** 一行战卡：名称 + 简介 + 战绩，点开在行内展开话术（与列表页的行样式一致） */
function Row({
  c,
  open,
  onToggle,
  admin,
  onEdit,
}: {
  c: Competitor
  open: boolean
  onToggle: () => void
  admin: boolean
  onEdit: () => void
}) {
  const del = useDeleteCompetitor()
  const { ask, dialog } = useConfirmAction()
  return (
    <li className="border-b border-zinc-100">
      {dialog}
      <div className="flex items-start gap-2 px-4 py-3 sm:px-5">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-label={`${c.name} 战卡`}
          className="flex min-w-0 flex-1 items-start gap-2.5 text-left"
        >
          <ChevronRight
            className={cn("mt-0.5 size-4 shrink-0 text-zinc-400 transition-transform", open && "rotate-90")}
          />
          <span className="min-w-0 text-sm">
            <span className="block font-medium">{c.name}</span>
            {c.summary ? <span className="block text-zinc-500">{c.summary}</span> : null}
            <CompetitorRecord c={c} />
          </span>
        </button>
        {admin ? (
          <div className="flex shrink-0 gap-1">
            <Button size="icon-sm" variant="ghost" aria-label={`编辑 ${c.name}`} onClick={onEdit}>
              <Pencil />
            </Button>
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label={`删除 ${c.name}`}
              disabled={del.isPending}
              onClick={() => ask({ ...deleteCompetitorConfirm(c.name), onConfirm: () => del.mutate(c.id) })}
            >
              <Trash2 />
            </Button>
          </div>
        ) : null}
      </div>
      {open ? (
        <div className="max-w-4xl pr-4 pb-4 pl-10 sm:pr-5 sm:pl-11">
          <BattleCardBody c={c} />
        </div>
      ) : null}
    </li>
  )
}

/** 竞品战卡：所有人可查（现场按客户原话搜），管理员维护；输赢战绩来自商机标注 */
export default function BattleCardsPage() {
  const { canConfigure: admin } = useSession()
  const [text, setText] = useState("")
  const q = useDebounced(text.trim(), 250)
  const query = useCompetitors(q)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState<Competitor | null | "new">(null)
  const toggle = (id: string) =>
    setExpanded((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  // 搜索时自动展开命中的战卡（只有一两张时直接看话术）
  const list = query.data ?? []
  const autoOpen = q !== "" && list.length <= 2

  return (
    <PageFrame
      title="竞品战卡"
      icon={Swords}
      actions={
        admin ? (
          <Button size="sm" onClick={() => setEditing("new")}>
            <Plus />
            新建战卡
          </Button>
        ) : null
      }
    >
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b border-zinc-100 px-4 py-2.5 sm:px-5">
          <div className="relative w-full sm:w-80">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-zinc-400" />
            <Input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="竞品名或客户原话，如：云上便宜、自己搭"
              aria-label="搜索竞品战卡"
              className="h-8 pl-8"
            />
          </div>
          {query.data ? (
            <span className="ml-auto text-xs text-zinc-500">
              共 <b className="text-zinc-800 tabular-nums">{list.length}</b> 张{admin ? null : " · 由管理员维护"}
            </span>
          ) : null}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {query.isPending ? (
            <div className="space-y-2 p-5">
              {Array.from({ length: 3 }, (_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : query.isError ? (
            <div className="p-5">
              <QueryError error={query.error} onRetry={() => void query.refetch()} feature="竞品战卡" />
            </div>
          ) : list.length === 0 ? (
            <EmptyState
              icon={Swords}
              title={q ? "没有匹配的战卡" : "还没有竞品战卡"}
              description={q ? "换个说法试试，或在 AI 工作台直接问「客户说……怎么回」" : undefined}
            />
          ) : (
            <ul aria-label="竞品战卡">
              {list.map((c) => (
                <Row
                  key={c.id}
                  c={c}
                  open={autoOpen || expanded.has(c.id)}
                  onToggle={() => toggle(c.id)}
                  admin={admin}
                  onEdit={() => setEditing(c)}
                />
              ))}
            </ul>
          )}
        </div>
      </div>
      {editing ? (
        <CompetitorForm
          key={editing === "new" ? "new" : editing.id}
          open
          onOpenChange={(o) => !o && setEditing(null)}
          initial={editing === "new" ? null : editing}
        />
      ) : null}
    </PageFrame>
  )
}
