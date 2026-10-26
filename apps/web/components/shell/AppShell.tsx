"use client"

import { useState, type CSSProperties, type ReactNode } from "react"

import { AppSidebar } from "@/components/shell/AppSidebar"
import { CommandMenu } from "@/components/shell/CommandMenu"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { useSidebarPreference } from "@/hooks/useSidebarPreference"

/** 侧栏宽度：展开 220px / 图标栏 56px（§10.4） */
const SIDEBAR_VARS = { "--sidebar-width": "220px", "--sidebar-width-icon": "56px" } as CSSProperties

/** 应用外壳：灰底导航 + 主区域（页面自己渲染白色面板） */
export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useSidebarPreference()
  const [searchOpen, setSearchOpen] = useState(false)
  return (
    <SidebarProvider
      open={open}
      onOpenChange={setOpen}
      style={SIDEBAR_VARS}
      className="bg-app h-dvh min-h-0 overflow-hidden"
    >
      <AppSidebar onSearch={() => setSearchOpen(true)} />
      <SidebarInset className="bg-app h-dvh min-w-0 overflow-hidden p-2 sm:p-3 lg:pl-0">{children}</SidebarInset>
      <CommandMenu open={searchOpen} onOpenChange={setSearchOpen} />
    </SidebarProvider>
  )
}
