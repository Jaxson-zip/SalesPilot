"use client"

import { useQuery } from "@tanstack/react-query"
import { ChevronsUpDown, KeyRound, LogOut, Shield, User, UserCheck, type LucideIcon } from "lucide-react"
import { usePathname, useRouter } from "next/navigation"
import { useState } from "react"
import { toast } from "sonner"

import { LetterAvatar } from "@/components/biz/Chip"
import { ChangePasswordDialog } from "@/components/shell/ChangePasswordDialog"
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
import { DEMO_USERS, fetchAuthOptions, isRole, ROLES } from "@/lib/session"
import type { Role } from "@/types/api"

const ROLE_ICONS: Record<Role, LucideIcon> = { sales: User, manager: UserCheck, admin: Shield }

/** 底部用户卡片：修改密码、退出登录；演示环境还可以切换演示账户 */
export function UserMenu() {
  const { role, user, switchRole, signOut } = useSession()
  const pathname = usePathname()
  const router = useRouter()
  const [changing, setChanging] = useState(false)
  const options = useQuery({ queryKey: ["auth", "options"], queryFn: fetchAuthOptions, staleTime: 5 * 60_000 })
  const demo = options.data?.demo_login ?? false

  const onRoleChange = (value: string) => {
    if (!isRole(value) || value === role) return
    if (isForbiddenPath(pathname, value)) router.push("/dashboard")
    switchRole(value)
      .then(() => toast.success(`已切换为 ${DEMO_USERS[value].title} · ${DEMO_USERS[value].name}`))
      .catch(() => toast.error("切换账户失败：无法连接 core，请稍后重试"))
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
            {/* 演示环境才能一键切换账户；正式使用（DEMO_LOGIN=false）只能退出后用别的账号登录 */}
            {demo ? (
              <>
                <DropdownMenuLabel className="text-xs text-zinc-500">切换演示账户</DropdownMenuLabel>
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
              </>
            ) : null}
            <DropdownMenuItem onSelect={() => setChanging(true)}>
              <KeyRound className="text-zinc-500" />
              修改密码
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={signOut}>
              <LogOut className="text-zinc-500" />
              退出登录
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <ChangePasswordDialog open={changing} onOpenChange={setChanging} />
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
