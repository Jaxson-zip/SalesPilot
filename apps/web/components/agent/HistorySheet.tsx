"use client"

import { GraduationCap, Loader2, MoreHorizontal, Pencil, Search, SquarePen, Trash2 } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useMemo, useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { useAgentThreads, useDeleteThread, useRenameThread } from "@/hooks/useAgentThreads"
import { isNotImplemented } from "@/lib/errors"
import { aiThreadHref, historyTime, toHistoryItems, type HistoryItem } from "@/lib/thread-history"
import { cn } from "@/lib/utils"

const DAY = 86_400_000

function groupOf(ts: number, now: Date = new Date()): string {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  if (ts >= today) return "今天"
  if (ts >= today - DAY) return "昨天"
  if (ts >= today - 6 * DAY) return "近 7 天"
  return "更早"
}

/** 一条会话：标题 + 时间；悬停（触屏常显）出现「更多」：重命名 / 删除，重命名时原地变成输入框 */
function HistoryRow({
  it,
  active,
  onPick,
  onRename,
  onDelete,
}: {
  it: HistoryItem
  active: boolean
  onPick: () => void
  onRename: (title: string) => void
  onDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(it.title)
  if (editing) {
    const done = (save: boolean) => {
      const title = draft.trim()
      if (save && title && title !== it.title) onRename(title)
      setEditing(false)
    }
    return (
      <Input
        autoFocus
        aria-label="会话名称"
        value={draft}
        maxLength={30}
        className="my-0.5 h-8"
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => done(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter") done(true)
          if (e.key === "Escape") {
            e.stopPropagation() // 只退出改名，不关面板
            done(false)
          }
        }}
      />
    )
  }
  return (
    <div
      className={cn(
        "group flex h-9 items-center rounded-md",
        active ? "bg-zinc-100 font-medium text-zinc-900" : "text-zinc-700 hover:bg-zinc-50",
      )}
    >
      <Link
        href={aiThreadHref(it.id)}
        onClick={onPick}
        aria-current={active ? "page" : undefined}
        className="flex h-full min-w-0 flex-1 items-center gap-2 pl-2.5"
      >
        {it.learn ? <GraduationCap className="size-3.5 shrink-0 text-zinc-400" aria-label="学习问答" /> : null}
        <span className="flex-1 truncate" title={it.title}>
          {it.title}
        </span>
        {it.running ? (
          <span className="inline-flex shrink-0 items-center gap-1 text-xs font-normal text-zinc-500">
            <Loader2 className="size-3 animate-spin" />
            生成中
          </span>
        ) : (
          <span className="shrink-0 text-xs font-normal text-zinc-400 tabular-nums">{historyTime(it.updatedAt)}</span>
        )}
      </Link>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`更多操作：${it.title}`}
            className="mx-1 inline-flex size-7 shrink-0 items-center justify-center rounded text-zinc-500 opacity-0 group-hover:opacity-100 hover:bg-zinc-200 focus-visible:opacity-100 data-[state=open]:opacity-100 max-md:opacity-100"
          >
            <MoreHorizontal className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-32">
          <DropdownMenuItem
            onSelect={() => {
              setDraft(it.title)
              setEditing(true)
            }}
          >
            <Pencil />
            重命名
          </DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onSelect={onDelete}>
            <Trash2 />
            删除
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

/**
 * 会话记录：从右侧滑出的面板（页面里只留对话区，左侧导航保持「工作区」菜单不变）。
 * 可按标题搜索、按日期分组；选中、新对话后自动关闭。当前会话由地址 `/ai?t=<id>` 决定。
 */
export function HistorySheet({
  open,
  onOpenChange,
  activeId,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  activeId: string | null
}) {
  const router = useRouter()
  const threads = useAgentThreads()
  const rename = useRenameThread()
  const remove = useDeleteThread()
  const { ask, dialog } = useConfirmAction()
  const [q, setQ] = useState("")
  const close = () => onOpenChange(false)
  // 打开时刷新：哪些会话还在后台生成、刚生成完的排到最前
  const { refetch } = threads
  useEffect(() => {
    if (open) void refetch()
  }, [open, refetch])

  const groups = useMemo(() => {
    const kw = q.trim().toLowerCase()
    const items = toHistoryItems(threads.data?.items ?? [])
      .filter((it) => !kw || it.title.toLowerCase().includes(kw))
      .sort((a, b) => b.updatedAt - a.updatedAt)
    const map = new Map<string, HistoryItem[]>()
    for (const it of items) {
      const g = groupOf(it.updatedAt)
      map.set(g, [...(map.get(g) ?? []), it])
    }
    return [...map.entries()]
  }, [threads.data, q])

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="w-[320px] gap-0 p-0 sm:max-w-[320px]" aria-label="会话记录">
          <SheetHeader className="gap-3 border-b border-zinc-100 p-4 pr-12">
            <SheetTitle className="text-base">会话记录</SheetTitle>
            <SheetDescription className="sr-only">按标题搜索，点一条打开</SheetDescription>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-zinc-400" />
                <Input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="搜索会话"
                  aria-label="搜索会话"
                  className="h-8 pl-8"
                />
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link href="/ai" onClick={close}>
                  <SquarePen />
                  新对话
                </Link>
              </Button>
            </div>
          </SheetHeader>
          <nav aria-label="会话记录" className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
            {threads.isPending ? (
              <div className="space-y-1.5 px-1 pt-3">
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : threads.isError ? (
              <div className="px-2 pt-3 text-xs text-zinc-400">
                {isNotImplemented(threads.error) ? (
                  "历史会话：后端开发中"
                ) : (
                  <>
                    加载失败，
                    <button type="button" className="text-zinc-600 underline" onClick={() => void threads.refetch()}>
                      重试
                    </button>
                  </>
                )}
              </div>
            ) : groups.length === 0 ? (
              <div className="px-2 pt-6 text-center text-sm text-zinc-400">{q ? "没有匹配的会话" : "还没有对话"}</div>
            ) : (
              groups.map(([g, list]) => (
                <div key={g}>
                  <div className="px-2.5 pt-3 pb-1 text-xs text-zinc-400">{g}</div>
                  {list.map((it) => (
                    <HistoryRow
                      key={it.id}
                      it={it}
                      active={it.id === activeId}
                      onPick={close}
                      onRename={(title) => rename.mutate({ id: it.id, title })}
                      onDelete={() =>
                        ask({
                          title: "删除会话",
                          description: `「${it.title}」的对话记录会一起删除，不能恢复。已生成的报价单、报销单等不受影响。`,
                          confirmLabel: "确认删除",
                          destructive: true,
                          onConfirm: () =>
                            remove.mutate(it.id, {
                              // 删的是正在看的会话：回到新对话
                              onSuccess: () => it.id === activeId && router.replace("/ai"),
                            }),
                        })
                      }
                    />
                  ))}
                </div>
              ))
            )}
          </nav>
        </SheetContent>
      </Sheet>
      {dialog}
    </>
  )
}
