"use client"

import {
  ArrowDown,
  ArrowDownUp,
  ChevronDown,
  Columns3,
  Download,
  List,
  ListFilter,
  Plus,
  Settings2,
  Upload,
  type LucideIcon,
} from "lucide-react"
import type { ComponentProps, ReactNode } from "react"

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

export interface ViewOption {
  value: string
  label: string
}

export interface FilterField {
  label: string
  icon: LucideIcon
}

interface MenuEntry {
  label: string
  icon: LucideIcon
}

const SORT_ITEMS: MenuEntry[] = [
  { label: "最近跟进（新→旧）", icon: ArrowDown },
  { label: "金额（高→低）", icon: ArrowDown },
  { label: "创建时间", icon: ArrowDown },
]

const OPTION_ITEMS: MenuEntry[] = [
  { label: "字段显示", icon: Columns3 },
  { label: "导入", icon: Upload },
  { label: "导出 CSV", icon: Download },
]

function GhostXs({ icon: Icon, label, ...props }: ComponentProps<"button"> & { icon: LucideIcon; label: string }) {
  return (
    <button
      type="button"
      title={label}
      {...props}
      className="focus-visible:ring-ring/50 inline-flex h-7 items-center gap-1 rounded-md px-2 text-zinc-600 outline-none hover:bg-zinc-100 focus-visible:ring-2"
    >
      <Icon className="size-3.5" />
      <span className="max-sm:hidden">{label}</span>
    </button>
  )
}

/** 右侧的筛选 / 排序 / 选项菜单（<640 只显示图标） */
function BarMenu({
  icon,
  label,
  title,
  items,
}: {
  icon: LucideIcon
  label: string
  title?: string
  items: MenuEntry[]
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <GhostXs icon={icon} label={label} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[200px]">
        {title ? <DropdownMenuLabel className="text-xs text-zinc-500">{title}</DropdownMenuLabel> : null}
        {items.map((it) => (
          <DropdownMenuItem key={it.label}>
            <it.icon className="text-zinc-500" />
            {it.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** 左侧视图切换 */
function ViewSwitcher({
  views,
  value,
  onValueChange,
  count,
}: Pick<ViewBarProps, "views" | "value" | "onValueChange" | "count">) {
  const current = views.find((v) => v.value === value) ?? views[0]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="focus-visible:ring-ring/50 inline-flex h-7 min-w-0 items-center gap-1.5 rounded-md px-2 outline-none hover:bg-zinc-100 focus-visible:ring-2"
        >
          <List className="size-3.5 shrink-0 text-zinc-500" />
          <span className="truncate font-medium">{current?.label}</span>
          {count !== undefined ? <span className="text-zinc-400 tabular-nums">· {count}</span> : null}
          <ChevronDown className="size-3.5 shrink-0 text-zinc-400" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[200px]">
        <DropdownMenuLabel className="text-xs text-zinc-500">视图</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={value} onValueChange={onValueChange}>
          {views.map((v) => (
            <DropdownMenuRadioItem key={v.value} value={v.value}>
              {v.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled>
          <Plus />
          新建视图
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

interface ViewBarProps {
  views: ViewOption[]
  value: string
  onValueChange: (value: string) => void
  count?: number
  fields: FilterField[]
  extra?: ReactNode
}

/** ViewBar：左侧视图切换（DropdownMenu），右侧筛选 / 排序 / 选项 */
export function ViewBar({ fields, extra, ...view }: ViewBarProps) {
  return (
    <div className="flex h-10 shrink-0 items-center justify-between gap-2 border-b border-zinc-200 px-2">
      <ViewSwitcher {...view} />
      <div className="flex shrink-0 items-center">
        {extra}
        <BarMenu icon={ListFilter} label="筛选" title="按字段筛选" items={fields} />
        <BarMenu icon={ArrowDownUp} label="排序" items={SORT_ITEMS} />
        <BarMenu icon={Settings2} label="选项" items={OPTION_ITEMS} />
      </div>
    </div>
  )
}
