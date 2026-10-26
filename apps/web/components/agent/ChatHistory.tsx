"use client"

import { Loader2, SquarePen } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { isNotImplemented } from "@/lib/errors"
import type { HistoryItem } from "@/lib/thread-history"
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

function groupOf(ts: number): string {
  const startOfToday = new Date().setHours(0, 0, 0, 0)
  if (ts >= startOfToday) return "今天"
  if (ts >= startOfToday - 6 * 86400000) return "7 天内"
  return "更早"
}

/** ChatHistory：左侧会话历史 240px（≥768 常驻；<768 由按钮浮出），数据来自 GET /api/agent/threads */
export function ChatHistory({
  items,
  status,
  activeId,
  loadingId,
  open,
  onNew,
  onSelect,
}: {
  items: HistoryItem[]
  status: HistoryStatus
  activeId: string | null
  /** 正在加载消息的会话 */
  loadingId?: string | null
  /** <768 时是否浮出 */
  open: boolean
  onNew: () => void
  onSelect: (id: string) => void
}) {
  const groups = new Map<string, HistoryItem[]>()
  for (const it of [...items].sort((a, b) => b.updatedAt - a.updatedAt)) {
    const g = groupOf(it.updatedAt)
    groups.set(g, [...(groups.get(g) ?? []), it])
  }
  return (
    <div
      className={cn(
        "w-[240px] shrink-0 flex-col border-r border-zinc-200 bg-white",
        open ? "absolute inset-y-0 left-0 z-20 flex shadow-xl" : "hidden",
        "md:static md:flex md:shadow-none",
      )}
    >
      <div className="p-2.5">
        <Button variant="outline" size="sm" className="w-full" onClick={onNew}>
          <SquarePen />
          新对话
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        <HistoryNotice status={status} empty={items.length === 0} />
        {[...groups.entries()].map(([g, list]) => (
          <div key={g}>
            <div className="px-2 pt-3 pb-1 text-xs text-zinc-400">{g}</div>
            {list.map((it) => (
              <button
                key={it.id}
                type="button"
                onClick={() => onSelect(it.id)}
                aria-current={it.id === activeId ? "true" : undefined}
                className={cn(
                  "flex h-8 w-full items-center rounded-md px-2 text-left",
                  it.id === activeId ? "bg-zinc-100 font-medium text-zinc-900" : "text-zinc-600 hover:bg-zinc-50",
                )}
              >
                <span className="flex-1 truncate" title={it.title}>
                  {it.title}
                </span>
                {it.id === loadingId ? <Loader2 className="size-3.5 shrink-0 animate-spin text-zinc-400" /> : null}
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
