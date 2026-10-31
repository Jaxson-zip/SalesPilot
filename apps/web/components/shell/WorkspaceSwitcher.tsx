"use client"

import { PanelLeftClose, PanelLeftOpen, X, Zap } from "lucide-react"
import Link from "next/link"

import { Button } from "@/components/ui/button"
import { useSidebar } from "@/components/ui/sidebar"

function Logo() {
  return (
    <span className="bg-primary text-primary-foreground inline-flex size-6 shrink-0 items-center justify-center rounded-md">
      <Zap className="size-3.5" />
    </span>
  )
}

/** 侧栏开关：展开时显示「收起」，图标栏时显示「展开」，抽屉里显示「关闭」 */
function ToggleButton() {
  const { state, isMobile, toggleSidebar, setOpenMobile } = useSidebar()
  const collapsed = state === "collapsed" && !isMobile
  const Icon = isMobile ? X : collapsed ? PanelLeftOpen : PanelLeftClose
  const label = isMobile ? "关闭导航" : `${collapsed ? "展开" : "收起"}侧边栏`
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      className="size-7 shrink-0 text-zinc-500 hover:bg-black/5"
      aria-label={label}
      title={isMobile ? label : `${label}（Ctrl B）`}
      onClick={() => (isMobile ? setOpenMobile(false) : toggleSidebar())}
    >
      <Icon />
    </Button>
  )
}

/** 品牌（点击回工作台）+ 侧栏开关。只有一个工作区，不放切换下拉 */
export function WorkspaceSwitcher() {
  const { state, isMobile } = useSidebar()
  const collapsed = state === "collapsed" && !isMobile
  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-2">
        <Link
          href="/dashboard"
          title="SalesPilot · 回到工作台"
          aria-label="SalesPilot，回到工作台"
          className="inline-flex size-9 items-center justify-center rounded-md hover:bg-black/5"
        >
          <Logo />
        </Link>
        <ToggleButton />
      </div>
    )
  }
  return (
    <div className="flex items-center gap-1">
      <Link
        href="/dashboard"
        title="回到工作台"
        className="flex h-9 min-w-0 flex-1 items-center gap-2 rounded-md px-2 hover:bg-black/5"
      >
        <Logo />
        <span className="flex-1 truncate text-left text-sm font-semibold text-zinc-900">SalesPilot</span>
      </Link>
      <ToggleButton />
    </div>
  )
}
