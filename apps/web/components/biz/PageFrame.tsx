"use client"

import { Menu, type LucideIcon } from "lucide-react"
import Link from "next/link"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { useSidebar } from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

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
  return (
    <div className="flex h-full min-w-0 flex-col">
      <div className="mb-1 flex h-10 min-w-0 shrink-0 items-center gap-2 px-1">
        {isMobile ? (
          <Button
            variant="ghost"
            size="icon-sm"
            className="-ml-1 text-zinc-600 hover:bg-black/5"
            title="打开导航"
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
        <div className="flex shrink-0 items-center gap-1.5">{actions}</div>
      </div>
      <div
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-zinc-200 bg-white",
          bodyClassName,
        )}
      >
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
