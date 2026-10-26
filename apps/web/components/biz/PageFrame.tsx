"use client"

import { Eye, Menu, type LucideIcon } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import type { ReactNode } from "react"

import { NotificationBell } from "@/components/shell/NotificationBell"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { useSidebar } from "@/components/ui/sidebar"
import { isBusinessPath } from "@/lib/nav"
import { isReadOnlyRole } from "@/lib/permissions"
import { cn } from "@/lib/utils"

/** 管理员打开业务页面时的「只读」提示（契约 §0） */
function ReadOnlyBanner() {
  return (
    <div
      role="note"
      aria-label="只读提示"
      className="flex h-9 shrink-0 items-center gap-2 border-b border-zinc-200 bg-zinc-50 px-4 text-zinc-600"
    >
      <Eye className="size-3.5 shrink-0 text-zinc-500" />
      <span className="shrink-0 font-medium text-zinc-800">只读</span>
      <span className="min-w-0 truncate">管理员负责系统配置，业务数据只读</span>
    </div>
  )
}

/**
 * PageFrame：Twenty 风格页面 —— 灰底标题行（40px）+ 白色圆角内容面板。
 * <1024 时标题行左侧显示 ☰，点击从左侧滑出导航抽屉。
 */
export function PageFrame({
  title,
  icon: Icon,
  crumb,
  actions,
  children,
  bodyClassName,
}: {
  title?: string
  icon?: LucideIcon
  /** 面包屑（详情页），传入后替代 title */
  crumb?: ReactNode
  actions?: ReactNode
  children: ReactNode
  bodyClassName?: string
}) {
  const { isMobile, setOpenMobile } = useSidebar()
  const { role } = useSession()
  const pathname = usePathname()
  const readOnly = isReadOnlyRole(role) && isBusinessPath(pathname)
  return (
    <div className="flex h-full min-w-0 flex-col">
      <div className="mb-1.5 flex h-10 min-w-0 shrink-0 items-center gap-2">
        {isMobile ? (
          <Button
            variant="ghost"
            size="icon-sm"
            className="text-zinc-600 hover:bg-black/5"
            title="打开导航"
            aria-label="打开导航"
            onClick={() => setOpenMobile(true)}
          >
            <Menu />
          </Button>
        ) : null}
        <div className="min-w-0 truncate">
          {crumb ?? (
            <span className="inline-flex items-center gap-1.5 font-medium text-zinc-800">
              {Icon ? <Icon className="size-4 text-zinc-500" /> : null}
              {title}
            </span>
          )}
        </div>
        <div className="flex-1" />
        <div className="flex shrink-0 items-center gap-1.5">
          <NotificationBell />
          {actions}
        </div>
      </div>
      <div
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-zinc-200 bg-white",
          bodyClassName,
        )}
      >
        {readOnly ? <ReadOnlyBanner /> : null}
        {children}
      </div>
    </div>
  )
}

/** 面包屑：父级链接 › 当前记录 */
export function Crumb({
  parent,
  href,
  icon: Icon,
  current,
}: {
  parent: string
  href: string
  icon: LucideIcon
  current: string
}) {
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5 text-zinc-500">
      <Link href={href} className="inline-flex shrink-0 items-center gap-1.5 hover:text-zinc-800">
        <Icon className="size-4" />
        {parent}
      </Link>
      <span className="text-zinc-300">/</span>
      <span className="truncate font-medium text-zinc-800">{current}</span>
    </span>
  )
}

/**
 * 标题行按钮（sm 32px）。<640 时只显示图标（文字放到 title 里）。
 * 每个视图最多 1 个 primary（黑色），放最右侧。
 */
export function FrameAction({
  icon: Icon,
  label,
  primary,
  href,
  onClick,
}: {
  icon?: LucideIcon
  label?: string
  primary?: boolean
  href?: string
  onClick?: () => void
}) {
  const iconOnly = !label
  const inner = (
    <>
      {Icon ? <Icon /> : null}
      {label ? <span className={cn(Icon && "max-sm:hidden")}>{label}</span> : null}
    </>
  )
  const className = cn(Icon && label && "max-sm:w-8 max-sm:px-0")
  const variant = primary ? "default" : iconOnly ? "ghost" : "outline"
  const size = iconOnly ? "icon-sm" : "sm"
  if (href) {
    return (
      <Button asChild variant={variant} size={size} className={className} title={label}>
        <Link href={href}>{inner}</Link>
      </Button>
    )
  }
  return (
    <Button variant={variant} size={size} className={className} title={label} onClick={onClick}>
      {inner}
    </Button>
  )
}
