"use client"

import { Check, ChevronsUpDown, PanelLeftClose, PanelLeftOpen, X, Zap } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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
  const title = isMobile ? "关闭导航" : `${collapsed ? "展开" : "收起"}侧边栏（Ctrl B）`
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      className="size-7 shrink-0 text-zinc-500 hover:bg-black/5"
      title={title}
      onClick={() => (isMobile ? setOpenMobile(false) : toggleSidebar())}
    >
      <Icon />
    </Button>
  )
}

/** 工作区切换（Logo + 名称 + 下拉）+ 侧栏开关 */
export function WorkspaceSwitcher() {
  const { state, isMobile } = useSidebar()
  const collapsed = state === "collapsed" && !isMobile
  const menu = (
    <DropdownMenuContent align="start" className="w-[200px]">
      <DropdownMenuLabel className="text-xs text-zinc-500">工作区</DropdownMenuLabel>
      <DropdownMenuItem>
        <Zap className="text-zinc-500" />
        <span className="flex-1">SalesPilot 演示</span>
        <Check />
      </DropdownMenuItem>
    </DropdownMenuContent>
  )

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              title="SalesPilot"
              className="inline-flex size-9 items-center justify-center rounded-md hover:bg-black/5"
            >
              <Logo />
            </button>
          </DropdownMenuTrigger>
          {menu}
        </DropdownMenu>
        <ToggleButton />
      </div>
    )
  }
  return (
    <div className="flex items-center gap-1">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button type="button" className="flex h-9 min-w-0 flex-1 items-center gap-2 rounded-md px-2 hover:bg-black/5">
            <Logo />
            <span className="flex-1 truncate text-left text-sm font-semibold text-zinc-900">SalesPilot</span>
            <ChevronsUpDown className="size-3.5 text-zinc-400" />
          </button>
        </DropdownMenuTrigger>
        {menu}
      </DropdownMenu>
      <ToggleButton />
    </div>
  )
}
