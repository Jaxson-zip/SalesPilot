"use client"

import { Search } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { useSession } from "@/components/shell/SessionProvider"
import { UserMenu } from "@/components/shell/UserMenu"
import { WorkspaceSwitcher } from "@/components/shell/WorkspaceSwitcher"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar"
import { canSee, isActivePath, NAV_GROUPS, type NavItem } from "@/lib/nav"

const itemClass =
  "h-7 gap-2 px-2 text-zinc-600 hover:bg-black/[0.04] data-[active=true]:text-zinc-900 [&>svg]:text-zinc-500 data-[active=true]:[&>svg]:text-zinc-800"

function Kbd({ children }: { children: string }) {
  return (
    <kbd className="ml-auto rounded border border-zinc-200 bg-white px-1 font-sans text-[10px] text-zinc-400 group-data-[collapsible=icon]:hidden">
      {children}
    </kbd>
  )
}

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const { isMobile, setOpenMobile } = useSidebar()
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={active} tooltip={item.label} className={itemClass}>
        <Link href={item.href} onClick={() => isMobile && setOpenMobile(false)}>
          <item.icon />
          <span>{item.label}</span>
        </Link>
      </SidebarMenuButton>
      {item.badge ? (
        <>
          <SidebarMenuBadge className="top-1 text-[11px] font-normal text-zinc-500">{item.badge}</SidebarMenuBadge>
          {/* 图标栏模式：数字换成红点 */}
          <span className="pointer-events-none absolute top-1 right-1 hidden size-1.5 rounded-full bg-red-500 group-data-[collapsible=icon]:block" />
        </>
      ) : null}
    </SidebarMenuItem>
  )
}

/**
 * 左侧导航（shadcn Sidebar，collapsible="icon"）：
 * ≥1280 默认展开 220px · 1024–1279 默认 56px 图标栏 · <1024 抽屉（Sheet）
 */
export function AppSidebar({ onSearch }: { onSearch: () => void }) {
  const pathname = usePathname()
  const { role } = useSession()
  return (
    <Sidebar collapsible="icon" className="group-data-[side=left]:border-r-0">
      <SidebarHeader className="px-2 pt-2.5 pb-1">
        <WorkspaceSwitcher />
      </SidebarHeader>
      <SidebarContent className="gap-0">
        {NAV_GROUPS.map((group, gi) => {
          const items = group.items.filter((i) => canSee(i, role))
          if (items.length === 0) return null
          return (
            <SidebarGroup key={group.label ?? gi} className="px-2 py-1.5">
              {group.label ? (
                <>
                  <SidebarSeparator className="mx-2 mb-2 hidden group-data-[collapsible=icon]:block" />
                  <SidebarGroupLabel className="h-7 px-2 text-xs font-normal text-zinc-400">
                    {group.label}
                  </SidebarGroupLabel>
                </>
              ) : null}
              <SidebarMenu className="gap-px">
                {gi === 0 ? (
                  <SidebarMenuItem>
                    <SidebarMenuButton tooltip="搜索（Ctrl K）" className={itemClass} onClick={onSearch}>
                      <Search />
                      <span>搜索</span>
                      <Kbd>Ctrl K</Kbd>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ) : null}
                {items.map((item) => (
                  <NavLink key={item.href} item={item} active={isActivePath(pathname, item.href)} />
                ))}
              </SidebarMenu>
            </SidebarGroup>
          )
        })}
      </SidebarContent>
      <SidebarFooter className="p-2">
        <UserMenu />
      </SidebarFooter>
    </Sidebar>
  )
}
