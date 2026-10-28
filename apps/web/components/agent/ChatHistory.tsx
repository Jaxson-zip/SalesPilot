"use client"

import { Loader2, MoreHorizontal, PanelLeftClose, Pencil, SquarePen, Trash2 } from "lucide-react"
import { useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { isNotImplemented } from "@/lib/errors"
import { historyTime, type HistoryItem } from "@/lib/thread-history"
import { cn } from "@/lib/utils"

export type { HistoryItem }

export interface HistoryStatus {
  isPending: boolean
  isError: boolean
  error: unknown
  refetch: () => unknown
}

/** 列表状态：加载中骨架、接口未实现「后端开发中」、失败可重试、空列表 */
function HistoryNotice({ status, empty }: { status: HistoryStatus; empty: boolean }) {
  if (status.isPending)
    return (
      <div className="space-y-1.5 px-1 pt-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-7 w-full" />
        ))}
      </div>
    )
  if (status.isError)
    return isNotImplemented(status.error) ? (
      <div className="px-2 pt-3 text-xs text-zinc-400">历史会话：后端开发中</div>
    ) : (
      <div className="px-2 pt-3 text-xs text-zinc-400">
        历史会话加载失败，
        <button type="button" className="text-zinc-600 underline" onClick={() => void status.refetch()}>
          重试
        </button>
      </div>
    )
  return empty ? <div className="px-2 pt-3 text-xs text-zinc-400">暂无历史会话</div> : null
}

/** 一条会话：标题 + 时间；悬停出现「更多」菜单（重命名 / 删除），重命名时原地变成输入框 */
function HistoryRow({
  it,
  active,
  loading,
  onSelect,
  onRename,
  onDelete,
}: {
  it: HistoryItem
  active: boolean
  loading: boolean
  onSelect: () => void
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
            e.stopPropagation()
            done(false)
          }
        }}
      />
    )
  }
  return (
    <div
      className={cn(
        "group flex h-8 items-center rounded-md",
        active ? "bg-zinc-100 font-medium text-zinc-900" : "text-zinc-600 hover:bg-zinc-50",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-current={active ? "true" : undefined}
        className="flex h-full min-w-0 flex-1 items-center gap-2 pl-2 text-left"
      >
        <span className="flex-1 truncate" title={it.title}>
          {it.title}
        </span>
        {loading ? (
          <Loader2 className="size-3.5 shrink-0 animate-spin text-zinc-400" />
        ) : (
          <span className="shrink-0 text-xs font-normal text-zinc-400 tabular-nums group-hover:hidden">
            {historyTime(it.updatedAt)}
          </span>
        )}
      </button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`更多操作：${it.title}`}
            className="mr-1 hidden size-6 shrink-0 items-center justify-center rounded text-zinc-500 group-hover:inline-flex hover:bg-zinc-200 focus-visible:inline-flex data-[state=open]:inline-flex"
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

function groupOf(ts: number): string {
  const startOfToday = new Date().setHours(0, 0, 0, 0)
  if (ts >= startOfToday) return "今天"
  if (ts >= startOfToday - 6 * 86400000) return "7 天内"
  return "更早"
}

/** ChatHistory：左侧会话记录 240px（≥768 固定、可收起；<768 浮层 + 遮罩），数据来自 GET /api/agent/threads */
export function ChatHistory({
  items,
  status,
  activeId,
  loadingId,
  pinned,
  overlay,
  onClose,
  onNew,
  onSelect,
  onRename,
  onDelete,
}: {
  items: HistoryItem[]
  status: HistoryStatus
  activeId: string | null
  /** 正在加载消息的会话 */
  loadingId?: string | null
  /** ≥768 是否固定显示 */
  pinned: boolean
  /** <768 是否浮出 */
  overlay: boolean
  /** 收起（≥768）/ 关闭浮层（<768） */
  onClose: () => void
  onNew: () => void
  onSelect: (id: string) => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
}) {
  const { ask, dialog } = useConfirmAction()
  const groups = new Map<string, HistoryItem[]>()
  for (const it of [...items].sort((a, b) => b.updatedAt - a.updatedAt)) {
    const g = groupOf(it.updatedAt)
    groups.set(g, [...(groups.get(g) ?? []), it])
  }
  return (
    <>
      {overlay ? <div aria-hidden className="absolute inset-0 z-10 bg-black/20 md:hidden" onClick={onClose} /> : null}
      <nav
        aria-label="会话记录"
        className={cn(
          "w-[240px] shrink-0 flex-col border-r border-zinc-200 bg-white",
          overlay ? "absolute inset-y-0 left-0 z-20 flex shadow-xl" : "hidden",
          pinned ? "md:static md:flex md:shadow-none" : "md:hidden",
        )}
      >
        <div className="flex items-center gap-1.5 p-2.5">
          <Button variant="outline" size="sm" className="flex-1" onClick={onNew}>
            <SquarePen />
            新对话
          </Button>
          <Button variant="ghost" size="icon-sm" title="收起会话记录" aria-label="收起" onClick={onClose}>
            <PanelLeftClose />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2">
          <HistoryNotice status={status} empty={items.length === 0} />
          {[...groups.entries()].map(([g, list]) => (
            <div key={g}>
              <div className="px-2 pt-3 pb-1 text-xs text-zinc-400">{g}</div>
              {list.map((it) => (
                <HistoryRow
                  key={it.id}
                  it={it}
                  active={it.id === activeId}
                  loading={it.id === loadingId}
                  onSelect={() => onSelect(it.id)}
                  onRename={(title) => onRename(it.id, title)}
                  onDelete={() =>
                    ask({
                      title: "删除会话",
                      description: `「${it.title}」的对话记录会一起删除，不能恢复。已生成的报价单、报销单等不受影响。`,
                      confirmLabel: "确认删除",
                      destructive: true,
                      onConfirm: () => onDelete(it.id),
                    })
                  }
                />
              ))}
            </div>
          ))}
        </div>
      </nav>
      {dialog}
    </>
  )
}
