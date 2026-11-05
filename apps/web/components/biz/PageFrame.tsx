"use client"

import { Eye, Menu, type LucideIcon } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import type { ReactNode } from "react"

import { NotificationBell } from "@/components/shell/NotificationBell"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { useSidebar } from "@/components/ui/sidebar"
import { isActivePath, isBusinessPath, navSiblings } from "@/lib/nav"
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
  const { role, solo } = useSession()
  const pathname = usePathname()
  const readOnly = isReadOnlyRole(role) && isBusinessPath(pathname)
  // 合并入口里的页面（如「系统」）：标题行换成同组页面的标签页
  const siblings = navSiblings(pathname, role, solo)
  return (
    <div className="flex h-full min-w-0 flex-col">
      <header className="mb-1.5 flex h-10 min-w-0 shrink-0 items-center gap-2">
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
          {/* 每页一个一级标题（读屏按标题跳转）：面包屑 / 标签页时标题只给读屏 */}
          {title && (crumb || siblings) ? <h1 className="sr-only">{title}</h1> : null}
          {crumb ??
            (siblings ? (
              <nav aria-label="页面切换" className="flex gap-1 overflow-x-auto">
                {siblings.map((t) => {
                  const on = isActivePath(pathname, t.href)
                  return (
                    <Link
                      key={t.href}
                      href={t.href}
                      aria-current={on ? "page" : undefined}
                      className={cn(
                        "inline-flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1 text-sm",
                        on ? "bg-white font-medium text-zinc-900 shadow-xs" : "text-zinc-500 hover:text-zinc-800",
                      )}
                    >
                      <t.icon className="size-4" />
                      {t.label}
                    </Link>
                  )
                })}
              </nav>
            ) : (
              <h1 className="inline-flex items-center gap-1.5 text-sm font-medium text-zinc-800">
                {Icon ? <Icon className="size-4 text-zinc-500" /> : null}
                {title}
              </h1>
            ))}
        </div>
        <div className="flex-1" />
        <div className="flex shrink-0 items-center gap-1.5">
          <NotificationBell />
          {actions}
        </div>
      </header>
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
/** 标题行按钮在窄屏只留图标（Tailwind 要写完整类名，不能拼接） */
export const COLLAPSE = {
  sm: { button: "max-sm:w-8 max-sm:px-0", label: "max-sm:hidden" },
  xl: { button: "max-xl:w-8 max-xl:px-0", label: "max-xl:hidden" },
} as const

export function FrameAction({
  icon: Icon,
  label,
  primary,
  href,
  onClick,
  collapse = "sm",
}: {
  icon?: LucideIcon
  label?: string
  primary?: boolean
  /** 窄于多宽时只显示图标：按钮多的详情页用 xl，免得把面包屑挤没 */
  collapse?: "sm" | "xl"
  href?: string
  onClick?: () => void
}) {
  const iconOnly = !label
  const inner = (
    <>
      {Icon ? <Icon /> : null}
      {label ? <span className={cn(Icon && COLLAPSE[collapse].label)}>{label}</span> : null}
    </>
  )
  const className = cn(Icon && label && COLLAPSE[collapse].button)
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
