import {
  BookOpen,
  Boxes,
  Building2,
  FileSignature,
  FileText,
  LayoutDashboard,
  Receipt,
  Scale,
  ScrollText,
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
  /** 显示待办数（审批：取待处理审批的真实数量） */
  pendingBadge?: boolean
}

export interface NavGroup {
  label?: string
  items: NavItem[]
}

const AI: NavItem = { href: "/ai", label: "AI 方案工作台", icon: Sparkles }
const DASHBOARD: NavItem = { href: "/dashboard", label: "工作台", icon: LayoutDashboard }
const CUSTOMERS: NavItem = { href: "/customers", label: "客户", icon: Building2 }
const PIPELINE: NavItem = { href: "/pipeline", label: "商机", icon: Target }
const QUOTES: NavItem = { href: "/quotes", label: "报价单", icon: FileText }
const CONTRACTS: NavItem = { href: "/contracts", label: "合同与提成", icon: FileSignature }
const EXPENSES: NavItem = { href: "/expenses", label: "报销", icon: Receipt }
const APPROVALS: NavItem = { href: "/approvals", label: "审批", icon: Stamp, pendingBadge: true }
const PACKS: NavItem = { href: "/settings/packs", label: "行业包配置", icon: Boxes }
const RULES: NavItem = { href: "/settings/rules", label: "业务规则", icon: Scale }
const AUDIT: NavItem = { href: "/settings/audit", label: "操作日志", icon: ScrollText }
/** 使用说明：所有角色可见，放在侧栏底部（不属于任何业务分组） */
export const HELP: NavItem = { href: "/help", label: "使用说明", icon: BookOpen }

/** 合同页的名称：主管侧重回款登记，其他角色侧重提成 */
export function contractsLabel(role: Role): string {
  return role === "manager" ? "合同与回款" : "合同与提成"
}

/**
 * 按角色分组的导航（契约 §0）：
 * 销售「工作区」；主管「工作区」+「团队管理」；管理员「业务总览（只读）」+「系统设置」。
 * 同一页面只出现在一个分组里；AI 方案工作台固定在最上方。
 */
export function navGroupsFor(role: Role): NavGroup[] {
  const top: NavGroup = { items: [AI] }
  if (role === "admin")
    return [
      top,
      { label: "业务总览（只读）", items: [DASHBOARD, CUSTOMERS, PIPELINE, QUOTES, CONTRACTS, EXPENSES] },
      { label: "系统设置", items: [RULES, PACKS, AUDIT] },
    ]
  if (role === "manager")
    return [
      top,
      { label: "工作区", items: [DASHBOARD, CUSTOMERS, PIPELINE, QUOTES, EXPENSES] },
      { label: "团队管理", items: [APPROVALS, { ...CONTRACTS, label: contractsLabel(role) }, AUDIT] },
    ]
  return [top, { label: "工作区", items: [DASHBOARD, CUSTOMERS, PIPELINE, QUOTES, CONTRACTS, EXPENSES] }]
}

/** 当前角色可见的全部导航项（命令面板用，含底部的使用说明） */
export function navItemsFor(role: Role): NavItem[] {
  return [...navGroupsFor(role).flatMap((g) => g.items), HELP]
}

const ALL_ITEMS: NavItem[] = [
  AI,
  DASHBOARD,
  CUSTOMERS,
  PIPELINE,
  QUOTES,
  CONTRACTS,
  EXPENSES,
  APPROVALS,
  RULES,
  PACKS,
  AUDIT,
]

export function isActivePath(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`)
}

/** 当前角色无权访问的路径（切换角色后需要跳回工作台） */
export function isForbiddenPath(pathname: string, role: Role): boolean {
  const visible = navItemsFor(role)
  return ALL_ITEMS.some((i) => isActivePath(pathname, i.href) && !visible.some((v) => v.href === i.href))
}

/** 业务页面（管理员打开时显示「只读」提示） */
export function isBusinessPath(pathname: string): boolean {
  return [AI, DASHBOARD, CUSTOMERS, PIPELINE, QUOTES, CONTRACTS, EXPENSES].some((i) => isActivePath(pathname, i.href))
}
