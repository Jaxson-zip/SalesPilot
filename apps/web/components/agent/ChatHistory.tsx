"use client"

import { SquarePen } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export interface HistoryItem {
  id: string
  title: string
  /** 毫秒时间戳，用于「今天 / 7 天内」分组 */
  updatedAt: number
}

function groupOf(ts: number): string {
  const startOfToday = new Date().setHours(0, 0, 0, 0)
  if (ts >= startOfToday) return "今天"
  if (ts >= startOfToday - 6 * 86400000) return "7 天内"
  return "更早"
}

/**
 * ChatHistory：左侧会话历史 240px（≥768 常驻；<768 由按钮浮出）。
 * TODO: 接入会话列表接口后替换为服务端数据。
 */
export function ChatHistory({
  items,
  activeId,
  open,
  onNew,
  onSelect,
}: {
  items: HistoryItem[]
  activeId: string | null
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
        {items.length === 0 ? <div className="px-2 pt-3 text-xs text-zinc-400">暂无历史会话</div> : null}
        {[...groups.entries()].map(([g, list]) => (
          <div key={g}>
            <div className="px-2 pt-3 pb-1 text-xs text-zinc-400">{g}</div>
            {list.map((it) => (
              <button
                key={it.id}
                type="button"
                onClick={() => onSelect(it.id)}
                className={cn(
                  "flex h-8 w-full items-center rounded-md px-2 text-left",
                  it.id === activeId ? "bg-zinc-100 font-medium text-zinc-900" : "text-zinc-600 hover:bg-zinc-50",
                )}
              >
                <span className="flex-1 truncate">{it.title}</span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
