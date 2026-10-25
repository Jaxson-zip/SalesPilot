"use client"

import { ChevronsUpDown, LogOut, Shield, User, UserCheck, type LucideIcon } from "lucide-react"
import { usePathname, useRouter } from "next/navigation"
import { toast } from "sonner"

import { LetterAvatar } from "@/components/biz/Chip"
import { useSession } from "@/components/shell/SessionProvider"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"
import { isForbiddenPath } from "@/lib/nav"
import { DEMO_USERS, isRole, logout, ROLES } from "@/lib/session"
import type { Role } from "@/types/api"

const ROLE_ICONS: Record<Role, LucideIcon> = { sales: User, manager: UserCheck, admin: Shield }

/** 底部用户卡片：切换演示角色（销售 / 主管 / 管理员） */
export function UserMenu() {
  const { role, user, switchRole } = useSession()
  const pathname = usePathname()
  const router = useRouter()

  const onRoleChange = (value: string) => {
    if (!isRole(value) || value === role) return
    if (isForbiddenPath(pathname, value)) router.push("/dashboard")
    switchRole(value)
      .then(() => toast.success(`已切换为 ${DEMO_USERS[value].title} · ${DEMO_USERS[value].name}`))
      .catch(() => toast.error("切换角色失败：无法连接 core，已在本地切换演示视图"))
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="h-10 gap-2 p-1.5 hover:bg-black/5"
              tooltip={`${user.name} · ${user.title}`}
            >
              <LetterAvatar name={user.name} className="size-7 text-xs" />
              <span className="min-w-0 flex-1 text-left">
                <span className="block truncate font-medium text-zinc-900">{user.name}</span>
                <span className="block text-xs text-zinc-500">{user.title}</span>
              </span>
              <ChevronsUpDown className="size-3.5 text-zinc-400" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-[204px]">
            <DropdownMenuLabel className="text-xs text-zinc-500">切换演示角色</DropdownMenuLabel>
            <DropdownMenuRadioGroup value={role} onValueChange={onRoleChange}>
              {ROLES.map((r) => {
                const Icon = ROLE_ICONS[r]
                return (
                  <DropdownMenuRadioItem key={r} value={r}>
                    <Icon className="text-zinc-500" />
                    {DEMO_USERS[r].title} · {DEMO_USERS[r].name}
                  </DropdownMenuRadioItem>
                )
              })}
            </DropdownMenuRadioGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => {
                logout()
                toast("已退出演示登录，下次请求会自动重新登录")
              }}
            >
              <LogOut className="text-zinc-500" />
              退出登录
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
