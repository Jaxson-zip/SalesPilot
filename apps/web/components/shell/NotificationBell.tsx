"use client"

import { Bell, CheckCheck, CheckCircle2, ClipboardCheck, Clock, UserRoundPlus, type LucideIcon } from "lucide-react"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Skeleton } from "@/components/ui/skeleton"
import { useMarkNotificationsRead, useNotifications } from "@/hooks/useNotifications"
import { isNotImplemented } from "@/lib/errors"
import { formatRelative } from "@/lib/format"
import { bellLabel, notificationHref, notificationMeta, unreadBadge, type NotificationTone } from "@/lib/notifications"
import { cn } from "@/lib/utils"
import type { NotificationItem } from "@/types/api"

const TONE_ICON: Record<NotificationTone, LucideIcon> = {
  approval: ClipboardCheck,
  result: CheckCircle2,
  assign: UserRoundPlus,
  task: Clock,
  other: Bell,
}

function Row({ n, onOpen }: { n: NotificationItem; onOpen: (n: NotificationItem) => void }) {
  const meta = notificationMeta(n.type)
  const Icon = TONE_ICON[meta.tone]
  return (
    <button
      type="button"
      onClick={() => onOpen(n)}
      className={cn(
        "flex w-full items-start gap-2.5 rounded-md px-2.5 py-2 text-left outline-none hover:bg-zinc-50 focus-visible:bg-zinc-50",
        !n.read && "bg-zinc-50/60",
      )}
    >
      <span className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full border border-zinc-200 text-zinc-500">
        <Icon className="size-3.5" aria-label={meta.label} />
      </span>
      <span className="min-w-0 flex-1">
        <span className={cn("block truncate", !n.read && "font-medium")}>{n.title}</span>
        {n.body ? <span className="block truncate text-xs text-zinc-500">{n.body}</span> : null}
        <span className="block text-xs text-zinc-400">
          {meta.label} · {formatRelative(n.created_at)}
        </span>
      </span>
      {!n.read ? <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-red-500" aria-label="未读" /> : null}
    </button>
  )
}

/** 通知铃铛（v3 §15）：放在每个页面的标题行右侧；未读数红点；下拉列表点击跳转并标记已读；每 60 秒刷新 */
export function NotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const q = useNotifications()
  const markRead = useMarkNotificationsRead()
  const unread = q.data?.unread ?? 0
  const badge = unreadBadge(unread)
  const items = q.data?.items ?? []

  const openItem = (n: NotificationItem) => {
    if (!n.read) markRead.mutate([n.id])
    const href = notificationHref(n.link)
    setOpen(false)
    if (href) router.push(href)
  }

  let body
  if (q.isPending) body = [0, 1, 2].map((i) => <Skeleton key={i} className="m-1.5 h-10" />)
  else if (q.isError && !q.data)
    body = (
      <div className="px-3 py-8 text-center text-zinc-500">
        {isNotImplemented(q.error) ? "通知接口后端开发中" : "通知加载失败"}
      </div>
    )
  else if (items.length === 0) body = <div className="px-3 py-8 text-center text-zinc-400">暂无通知</div>
  else body = items.map((n) => <Row key={n.id} n={n} onOpen={openItem} />)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          className="relative text-zinc-600 hover:bg-black/5"
          aria-label={bellLabel(unread)}
          title="通知"
        >
          <Bell />
          {badge ? (
            <span className="absolute -top-0.5 -right-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] leading-none font-medium text-white tabular-nums">
              {badge}
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[340px] max-w-[calc(100vw-24px)] p-0">
        <div className="flex h-10 items-center justify-between border-b border-zinc-100 px-3">
          <span className="font-medium">通知</span>
          {unread > 0 ? (
            <Button
              variant="ghost"
              size="xs"
              className="h-7 text-zinc-600"
              disabled={markRead.isPending}
              onClick={() => markRead.mutate(undefined)}
            >
              <CheckCheck />
              全部已读
            </Button>
          ) : null}
        </div>
        <div className="max-h-[420px] overflow-y-auto p-1">{body}</div>
      </PopoverContent>
    </Popover>
  )
}
