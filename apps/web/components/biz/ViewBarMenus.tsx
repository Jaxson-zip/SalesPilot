"use client"

import { ArrowDownUp, Columns3, Download, ListFilter, Settings2, X, type LucideIcon } from "lucide-react"
import type { ComponentProps } from "react"

import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  filterChips,
  SORT_OPTIONS,
  toggleFilter,
  toggleHidden,
  type ActiveFilters,
  type FilterDef,
  type SortKey,
} from "@/lib/list-view"
import { cn } from "@/lib/utils"

/** ViewBar 右侧菜单需要的状态（由 hooks/useListView 提供） */
export interface ViewBarListProps {
  // FilterDef 的行类型在这里不重要，只用到 id / label / options
  filters: FilterDef<never>[]
  activeFilters: ActiveFilters
  onFiltersChange: (next: ActiveFilters) => void
  sort: SortKey
  onSortChange: (key: SortKey) => void
  onExport?: () => void
  /** 可隐藏的列；不传则「选项」里没有「显示字段」 */
  columns?: { id: string; label: string }[]
  hiddenColumns: string[]
  onHiddenColumnsChange: (next: string[]) => void
}

export function GhostXs({
  icon: Icon,
  label,
  active,
  ...props
}: ComponentProps<"button"> & { icon: LucideIcon; label: string; active?: boolean }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      {...props}
      className={cn(
        "focus-visible:ring-ring/50 inline-flex h-7 items-center gap-1 rounded-md px-2 text-zinc-600 outline-none hover:bg-zinc-100 focus-visible:ring-2",
        active && "bg-zinc-100 text-zinc-900",
      )}
    >
      <Icon className="size-3.5" />
      <span className="max-sm:hidden">{label}</span>
    </button>
  )
}

const keepOpen = (e: Event) => e.preventDefault()

export function FilterMenu({ filters, activeFilters, onFiltersChange }: ViewBarListProps) {
  const count = Object.values(activeFilters).reduce((s, v) => s + v.length, 0)
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <GhostXs icon={ListFilter} label={count ? `筛选 ${count}` : "筛选"} active={count > 0} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[200px]">
        <DropdownMenuLabel className="text-xs text-zinc-500">按字段筛选</DropdownMenuLabel>
        {filters.map((f) => (
          <DropdownMenuSub key={f.id}>
            <DropdownMenuSubTrigger>
              <span className="flex-1">{f.label}</span>
              {activeFilters[f.id]?.length ? (
                <span className="text-xs text-zinc-500 tabular-nums">{activeFilters[f.id].length}</span>
              ) : null}
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="max-h-72 w-[180px] overflow-y-auto">
              {f.options.length === 0 ? <div className="px-2 py-1.5 text-xs text-zinc-400">暂无可选值</div> : null}
              {f.options.map((o) => (
                <DropdownMenuCheckboxItem
                  key={o.value}
                  checked={activeFilters[f.id]?.includes(o.value) ?? false}
                  onSelect={keepOpen}
                  onCheckedChange={() => onFiltersChange(toggleFilter(activeFilters, f.id, o.value))}
                >
                  {o.label}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        ))}
        {count ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => onFiltersChange({})}>
              <X className="text-zinc-500" />
              清除全部筛选
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function SortMenu({ sort, onSortChange }: Pick<ViewBarListProps, "sort" | "onSortChange">) {
  const current = SORT_OPTIONS.find((o) => o.value === sort)
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <GhostXs
          icon={ArrowDownUp}
          label={sort === "default" ? "排序" : (current?.label ?? "排序")}
          active={sort !== "default"}
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[180px]">
        <DropdownMenuLabel className="text-xs text-zinc-500">排序（当前页）</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={sort}
          onValueChange={(v) => {
            const hit = SORT_OPTIONS.find((o) => o.value === v)
            if (hit) onSortChange(hit.value)
          }}
        >
          {SORT_OPTIONS.map((o) => (
            <DropdownMenuRadioItem key={o.value} value={o.value}>
              {o.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function OptionsMenu({
  onExport,
  columns,
  hiddenColumns,
  onHiddenColumnsChange,
}: Pick<ViewBarListProps, "onExport" | "columns" | "hiddenColumns" | "onHiddenColumnsChange">) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <GhostXs icon={Settings2} label="选项" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[200px]">
        {columns?.length ? (
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <Columns3 className="text-zinc-500" />
              显示字段
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-[180px]">
              {columns.map((c) => (
                <DropdownMenuCheckboxItem
                  key={c.id}
                  checked={!hiddenColumns.includes(c.id)}
                  onSelect={keepOpen}
                  onCheckedChange={() => onHiddenColumnsChange(toggleHidden(hiddenColumns, c.id))}
                >
                  {c.label}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        ) : null}
        {onExport ? (
          <DropdownMenuItem onSelect={onExport}>
            <Download className="text-zinc-500" />
            导出 CSV
          </DropdownMenuItem>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** 生效的筛选：ViewBar 下方一行可清除的标签 */
export function FilterChips({ filters, activeFilters, onFiltersChange }: ViewBarListProps) {
  const chips = filterChips(filters, activeFilters)
  if (chips.length === 0) return null
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-b border-zinc-200 px-3 py-2">
      {chips.map((c) => (
        <span
          key={`${c.id}:${c.value}`}
          className="inline-flex h-6 items-center gap-1 rounded-md bg-zinc-100 pr-1 pl-2 text-xs text-zinc-700"
        >
          {c.label}
          <button
            type="button"
            aria-label={`清除筛选 ${c.label}`}
            onClick={() => onFiltersChange(toggleFilter(activeFilters, c.id, c.value))}
            className="inline-flex size-4 items-center justify-center rounded text-zinc-500 hover:bg-zinc-200 hover:text-zinc-800"
          >
            <X className="size-3" />
          </button>
        </span>
      ))}
      <button
        type="button"
        onClick={() => onFiltersChange({})}
        className="h-6 rounded-md px-1.5 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800"
      >
        清除全部
      </button>
    </div>
  )
}
