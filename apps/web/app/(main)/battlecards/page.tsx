"use client"

import { ChevronDown, Pencil, Plus, Search, Swords, Trash2 } from "lucide-react"
import { useState } from "react"

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
import { cn } from "@/lib/utils"

function Card({
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
  return (
    <li className="rounded-lg border border-zinc-200">
      <div className="flex items-start gap-2 p-3 sm:p-4">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-label={`${c.name} 战卡`}
          className="flex min-w-0 flex-1 items-start gap-2 text-left"
        >
          <ChevronDown
            className={cn("mt-0.5 size-4 shrink-0 text-zinc-400 transition-transform", !open && "-rotate-90")}
          />
          <span className="min-w-0">
            <span className="block font-medium">{c.name}</span>
            {c.summary ? <span className="block text-sm text-zinc-500">{c.summary}</span> : null}
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
              onClick={() => {
                if (window.confirm(`删除「${c.name}」战卡？已标注的商机会移除这个竞品。`)) del.mutate(c.id)
              }}
            >
              <Trash2 />
            </Button>
          </div>
        ) : null}
      </div>
      {open ? (
        <div className="border-t border-zinc-100 p-3 sm:p-4">
          <BattleCardBody c={c} />
        </div>
      ) : null}
    </li>
  )
}

/** 竞品战卡：所有人可查（现场按客户原话搜），管理员维护；输赢战绩来自商机标注 */
export default function BattleCardsPage() {
  const { role } = useSession()
  const admin = role === "admin"
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
      <div className="mx-auto w-full max-w-4xl space-y-3 p-4 sm:p-5">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-zinc-400" />
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="输入竞品名或客户原话，例如：云上便宜、自己搭"
            aria-label="搜索竞品战卡"
            className="h-10 pl-9"
          />
        </div>
        {query.isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : query.isError ? (
          <QueryError error={query.error} onRetry={() => void query.refetch()} feature="竞品战卡" />
        ) : list.length === 0 ? (
          <EmptyState
            icon={Swords}
            title={q ? "没有匹配的战卡" : "还没有竞品战卡"}
            description={q ? "换个说法试试，或在 AI 工作台直接问「客户说……怎么回」" : undefined}
          />
        ) : (
          <ul aria-label="竞品战卡" className="space-y-2">
            {list.map((c) => (
              <Card
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
