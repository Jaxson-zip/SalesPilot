"use client"

import { ChevronDown, List } from "lucide-react"
import type { ReactNode } from "react"

import { FilterChips, FilterMenu, OptionsMenu, SortMenu, type ViewBarListProps } from "@/components/biz/ViewBarMenus"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

export interface ViewOption {
  value: string
  label: string
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
          {count !== undefined ? <span className="text-zinc-500 tabular-nums">· {count}</span> : null}
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
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

interface ViewBarProps {
  views: ViewOption[]
  value: string
  onValueChange: (value: string) => void
  count?: number
  /** 筛选 / 排序 / 选项（hooks/useListView 的 bar）；不传则右侧不显示这些菜单 */
  list?: ViewBarListProps
  extra?: ReactNode
}

/** ViewBar：左侧视图切换（DropdownMenu），右侧筛选 / 排序 / 选项；下方显示生效的筛选标签 */
export function ViewBar({ list, extra, ...view }: ViewBarProps) {
  return (
    <>
      <div className="flex h-10 shrink-0 items-center justify-between gap-2 border-b border-zinc-200 px-2">
        <ViewSwitcher {...view} />
        <div className="flex shrink-0 items-center">
          {extra}
          {list ? (
            <>
              <FilterMenu {...list} />
              <SortMenu sort={list.sort} onSortChange={list.onSortChange} />
              <OptionsMenu {...list} />
            </>
          ) : null}
        </div>
      </div>
      {list ? <FilterChips {...list} /> : null}
    </>
  )
}
