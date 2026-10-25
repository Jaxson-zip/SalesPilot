import {
  Boxes,
  Building2,
  FileSignature,
  FileText,
  LayoutDashboard,
  Receipt,
  Sparkles,
  Stamp,
  Target,
  type LucideIcon,
} from "lucide-react"

import type { Role } from "@/types/api"

export interface NavItem {
  href: string
  label: string
  icon: LucideIcon
  /** 只有这些角色可见；不填表示所有角色 */
  roles?: Role[]
  /** 待办数（演示数据） */
  badge?: number
}

export interface NavGroup {
  label?: string
  items: NavItem[]
}

/** 导航结构与原型 NAV 一致（「组件规范」页只在原型里存在，不进正式应用） */
export const NAV_GROUPS: NavGroup[] = [
  { items: [{ href: "/ai", label: "AI 方案工作台", icon: Sparkles }] },
  {
    label: "工作区",
    items: [
      { href: "/dashboard", label: "工作台", icon: LayoutDashboard },
      { href: "/customers", label: "客户", icon: Building2 },
      { href: "/pipeline", label: "商机", icon: Target },
      { href: "/quotes", label: "报价单", icon: FileText },
      { href: "/contracts", label: "合同与提成", icon: FileSignature },
      { href: "/expenses", label: "报销", icon: Receipt },
    ],
  },
  {
    label: "管理",
    items: [
      { href: "/approvals", label: "审批", icon: Stamp, roles: ["manager"], badge: 3 },
      { href: "/settings/packs", label: "行业包配置", icon: Boxes, roles: ["admin"] },
    ],
  },
]

export function canSee(item: NavItem, role: Role): boolean {
  return !item.roles || item.roles.includes(role)
}

export function isActivePath(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`)
}

/** 当前角色无权访问的路径（切换角色后需要跳回工作台） */
export function isForbiddenPath(pathname: string, role: Role): boolean {
  return NAV_GROUPS.some((g) => g.items.some((i) => isActivePath(pathname, i.href) && !canSee(i, role)))
}
