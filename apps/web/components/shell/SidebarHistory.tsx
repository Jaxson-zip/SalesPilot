"use client"

import { Loader2, MoreHorizontal, Pencil, SquarePen, Trash2 } from "lucide-react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useMemo, useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  useSidebar,
} from "@/components/ui/sidebar"
import { useAgentThreads, useDeleteThread, useRenameThread } from "@/hooks/useAgentThreads"
import { isNotImplemented } from "@/lib/errors"
import { aiThreadHref, historyTime, toHistoryItems, type HistoryItem } from "@/lib/thread-history"

const itemClass =
  "h-7 gap-2 px-2 text-zinc-600 hover:bg-black/[0.04] data-[active=true]:text-zinc-900 [&>svg]:text-zinc-500"

/** 一条会话：标题 + 时间；悬停出现「更多」（重命名 / 删除），重命名时原地变成输入框 */
function HistoryRow({
  it,
  active,
  onNavigate,
  onRename,
  onDelete,
}: {
  it: HistoryItem
  active: boolean
  onNavigate: () => void
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
      <SidebarMenuItem>
        <Input
          autoFocus
          aria-label="会话名称"
          value={draft}
          maxLength={30}
          className="h-7 bg-white px-2"
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
      </SidebarMenuItem>
    )
  }
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={active} className={itemClass}>
        <Link href={aiThreadHref(it.id)} onClick={onNavigate} aria-current={active ? "page" : undefined}>
          <span className="flex-1 truncate" title={it.title}>
            {it.title}
          </span>
          <span className="shrink-0 text-[11px] text-zinc-400 tabular-nums group-focus-within/menu-item:invisible group-hover/menu-item:invisible">
            {historyTime(it.updatedAt)}
          </span>
        </Link>
      </SidebarMenuButton>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <SidebarMenuAction showOnHover aria-label={`更多操作：${it.title}`} className="top-1 hover:bg-black/[0.06]">
            <MoreHorizontal />
          </SidebarMenuAction>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="right" align="start" className="w-32">
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
    </SidebarMenuItem>
  )
}

/**
 * AI 工作台的会话记录，放在左侧导航里（只在 /ai 显示），不再在页面里另开一栏：
 * 页面少一列，对话区更宽；手机上随导航抽屉一起打开。
 * 当前会话由地址 `/ai?t=<id>` 决定，页面监听地址加载会话。
 */
export function SidebarHistory() {
  const { isMobile, setOpenMobile } = useSidebar()
  const activeId = useSearchParams().get("t")
  const router = useRouter()
  const threads = useAgentThreads()
  const rename = useRenameThread()
  const remove = useDeleteThread()
  const { ask, dialog } = useConfirmAction()
  const items = useMemo(
    () => [...toHistoryItems(threads.data?.items ?? [])].sort((a, b) => b.updatedAt - a.updatedAt),
    [threads.data],
  )
  const close = () => isMobile && setOpenMobile(false)

  return (
    <>
      <SidebarGroup className="px-2 py-1.5">
        <SidebarMenu className="gap-px">
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="新对话" className={itemClass}>
              <Link href="/ai" onClick={close}>
                <SquarePen />
                <span>新对话</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroup>
      <nav aria-label="会话记录" className="min-h-0 group-data-[collapsible=icon]:hidden">
        <SidebarGroup className="px-2 py-1.5">
          <SidebarGroupLabel className="h-7 px-2 text-xs font-normal text-zinc-400">
            最近对话
            {threads.isFetching && !threads.isPending ? <Loader2 className="ml-1 size-3 animate-spin" /> : null}
          </SidebarGroupLabel>
          <SidebarMenu className="gap-px">
            {threads.isPending ? (
              [0, 1, 2].map((i) => (
                <SidebarMenuItem key={i}>
                  <SidebarMenuSkeleton className="h-7" />
                </SidebarMenuItem>
              ))
            ) : threads.isError ? (
              <div className="px-2 text-xs text-zinc-400">
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
            ) : items.length === 0 ? (
              <div className="px-2 text-xs text-zinc-400">还没有对话</div>
            ) : (
              items.map((it) => (
                <HistoryRow
                  key={it.id}
                  it={it}
                  active={it.id === activeId}
                  onNavigate={close}
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
              ))
            )}
          </SidebarMenu>
        </SidebarGroup>
      </nav>
      {dialog}
    </>
  )
}
