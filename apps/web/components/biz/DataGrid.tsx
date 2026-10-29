"use client"

import { getCoreRowModel, useReactTable, type ColumnDef, type Table } from "@tanstack/react-table"
import { ChevronLeft, ChevronRight, Plus, type LucideIcon } from "lucide-react"
import { useMemo, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Skeleton } from "@/components/ui/skeleton"
import type { SelectionState } from "@/lib/selection"
import { cn } from "@/lib/utils"

export interface GridColumn<T> {
  id: string
  label: string
  icon: LucideIcon
  cell: (row: T) => ReactNode
  /** 数字列：右对齐 + tabular-nums */
  align?: "right"
  /** 次要列（原型里的 `lg`）：<1024 隐藏；"wide" 表示列多的表格里 <1360 就隐藏 */
  secondary?: boolean | "wide"
  /** 状态列：手机卡片里放右上角 */
  status?: boolean
  /** 列宽（Tailwind 类，如 w-[220px]）；不填则平分剩余宽度 */
  width?: string
}

interface DataGridProps<T> {
  columns: GridColumn<T>[]
  data: T[]
  getRowId: (row: T) => string
  loading?: boolean
  total?: number
  onAddRow?: () => void
  /** 空数据时显示（加载中不显示） */
  empty?: ReactNode
  /** 多选（批量操作）：不传则不显示勾选列；手机卡片列表不支持多选 */
  selection?: SelectionState
  onSelectionChange?: (next: SelectionState) => void
  /** 服务端分页：底栏显示页码和翻页按钮 */
  pagination?: Pagination
}

export interface Pagination {
  page: number
  pageSize: number
  onPageChange: (page: number) => void
}

const hideSecondary = (c: { secondary?: boolean | "wide" }) =>
  c.secondary === "wide" ? "hidden min-[1360px]:table-cell" : c.secondary ? "hidden lg:table-cell" : ""
const SKELETON_ROWS = Array.from({ length: 8 }, (_, i) => i)
/** 勾选列：左边距 12px（离面板边缘），勾选框 16px，右侧 8px 与首列内容隔开 */
const CHECK_CELL = "w-9 border-b pl-3 pr-2 text-left align-middle"
const NO_SELECTION: SelectionState = {}

/**
 * DataGrid：Twenty 网格。表头 32px、行高 34px、竖向分隔线、首列勾选（可选）、末行「+ 新增一条」。
 * 不允许横向滚动：table-fixed + 单元格截断；<1024 隐藏次要列；<768 改为卡片列表。
 */
export function DataGrid<T>({
  columns,
  data,
  getRowId,
  loading,
  total,
  onAddRow,
  empty,
  selection,
  pagination,
  onSelectionChange,
}: DataGridProps<T>) {
  const selectable = Boolean(onSelectionChange)
  const rowSelection = selection ?? NO_SELECTION
  const defs = useMemo<ColumnDef<T>[]>(
    () => columns.map((c) => ({ id: c.id, header: c.label, cell: ({ row }) => c.cell(row.original) })),
    [columns],
  )
  const table = useReactTable({
    data,
    columns: defs,
    getRowId,
    state: { rowSelection },
    enableRowSelection: selectable,
    onRowSelectionChange: (u) => onSelectionChange?.(typeof u === "function" ? u(rowSelection) : u),
    getCoreRowModel: getCoreRowModel(),
  })
  const showEmpty = !loading && data.length === 0 && empty

  return (
    <>
      {showEmpty ? (
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">{empty}</div>
      ) : (
        <>
          <div className="hidden min-h-0 flex-1 overflow-x-hidden overflow-y-auto md:block">
            <table className="w-full table-fixed border-collapse">
              <GridHead table={table} columns={columns} selectable={selectable} />
              <GridBody table={table} columns={columns} loading={loading} onAddRow={onAddRow} selectable={selectable} />
            </table>
          </div>
          <GridCards columns={columns} data={data} getRowId={getRowId} loading={loading} />
        </>
      )}
      <div className="flex h-8 shrink-0 items-center border-t border-zinc-200 px-3 text-xs text-zinc-500">
        <span>{loading ? "加载中…" : `共 ${total ?? data.length} 条`}</span>
        {pagination && total !== undefined ? <Pager {...pagination} total={total} /> : null}
      </div>
    </>
  )
}

function GridHead<T>({
  table,
  columns,
  selectable,
}: {
  table: Table<T>
  columns: GridColumn<T>[]
  selectable: boolean
}) {
  const all = table.getIsAllRowsSelected() ? true : table.getIsSomeRowsSelected() ? "indeterminate" : false
  return (
    <thead className="sticky top-0 z-10 bg-white">
      <tr className="h-8 text-zinc-500">
        {selectable ? (
          <th className={cn(CHECK_CELL, "border-zinc-200")}>
            <Checkbox
              aria-label="全选"
              className="align-middle"
              checked={all}
              onCheckedChange={(v) => table.toggleAllRowsSelected(v === true)}
            />
          </th>
        ) : null}
        {columns.map((c, i) => (
          <th
            key={c.id}
            className={cn(
              "overflow-hidden border-b border-zinc-200 px-2 text-left font-normal whitespace-nowrap",
              // 最后一列不画右边线（表格右侧不留空列）；没有勾选列时首列左边距 12px
              i < columns.length - 1 && "border-r",
              !selectable && i === 0 && "pl-3",
              c.width,
              hideSecondary(c),
            )}
          >
            <span
              className={cn("inline-flex max-w-full items-center gap-1.5", c.align === "right" && "w-full justify-end")}
            >
              <c.icon className="size-3.5 shrink-0" />
              <span className="truncate">{c.label}</span>
            </span>
          </th>
        ))}
      </tr>
    </thead>
  )
}

function GridBody<T>({
  table,
  columns,
  loading,
  onAddRow,
  selectable,
}: {
  table: Table<T>
  columns: GridColumn<T>[]
  loading?: boolean
  onAddRow?: () => void
  selectable: boolean
}) {
  const cellBase = "overflow-hidden border-b border-zinc-100 px-2 whitespace-nowrap"
  const cellCls = (c: GridColumn<T>, i: number) =>
    cn(cellBase, i < columns.length - 1 && "border-r", !selectable && i === 0 && "pl-3", hideSecondary(c))
  if (loading) {
    return (
      <tbody>
        {SKELETON_ROWS.map((i) => (
          <tr key={i} className="h-[34px]">
            {selectable ? <td className={cn(CHECK_CELL, "border-zinc-100")} /> : null}
            {columns.map((c, ci) => (
              <td key={c.id} className={cellCls(c, ci)}>
                <Skeleton className="h-3.5 w-3/4" />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    )
  }
  return (
    <tbody>
      {table.getRowModel().rows.map((row) => (
        <tr
          key={row.id}
          className="h-[34px] hover:bg-zinc-50 data-[state=selected]:bg-zinc-50"
          data-state={row.getIsSelected() ? "selected" : undefined}
        >
          {selectable ? (
            <td className={cn(CHECK_CELL, "border-zinc-100")}>
              <Checkbox
                aria-label="选择该行"
                className="align-middle"
                checked={row.getIsSelected()}
                onCheckedChange={(v) => row.toggleSelected(v === true)}
              />
            </td>
          ) : null}
          {columns.map((c, ci) => (
            <td key={c.id} className={cn(cellCls(c, ci), c.align === "right" && "text-right tabular-nums")}>
              <div className="truncate">{c.cell(row.original)}</div>
            </td>
          ))}
        </tr>
      ))}
      {onAddRow ? (
        <tr className="h-[34px] text-zinc-400">
          {selectable ? <td className="border-b border-zinc-100" /> : null}
          <td colSpan={columns.length} className={cn("border-b border-zinc-100 px-2", !selectable && "pl-3")}>
            <button type="button" onClick={onAddRow} className="inline-flex items-center gap-1.5 hover:text-zinc-700">
              <Plus className="size-3.5" />
              新增一条
            </button>
          </td>
        </tr>
      ) : null}
    </tbody>
  )
}

/** 手机（<768）：卡片列表。第一列作标题，状态放右上角，其余字段两列排布 */
function GridCards<T>({
  columns,
  data,
  getRowId,
  loading,
}: Pick<DataGridProps<T>, "columns" | "data" | "getRowId" | "loading">) {
  const [first, ...rest] = columns
  const status = columns.find((c) => c.status)
  const fields = rest.filter((c) => c !== status)
  return (
    <div className="min-h-0 flex-1 divide-y divide-zinc-100 overflow-x-hidden overflow-y-auto md:hidden">
      {loading
        ? SKELETON_ROWS.slice(0, 5).map((i) => (
            <div key={i} className="space-y-2.5 px-3 py-3">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-3.5 w-3/4" />
            </div>
          ))
        : data.map((row) => (
            <div key={getRowId(row)} className="px-3 py-3 active:bg-zinc-50">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0 truncate font-medium">{first.cell(row)}</div>
                {status ? <div className="shrink-0">{status.cell(row)}</div> : null}
              </div>
              <div className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-2">
                {fields.map((c) => (
                  <div key={c.id} className="min-w-0">
                    <div className="text-[11px] text-zinc-400">{c.label}</div>
                    <div className={cn("mt-0.5 truncate", c.align === "right" && "tabular-nums")}>{c.cell(row)}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
    </div>
  )
}

/** 底栏翻页：只有一页时不显示 */
function Pager({ page, pageSize, total, onPageChange }: Pagination & { total: number }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (pages <= 1) return null
  return (
    <nav aria-label="翻页" className="ml-auto flex items-center gap-1">
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label="上一页"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        <ChevronLeft />
      </Button>
      <span className="tabular-nums" aria-live="polite">
        第 {page} / {pages} 页
      </span>
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label="下一页"
        disabled={page >= pages}
        onClick={() => onPageChange(page + 1)}
      >
        <ChevronRight />
      </Button>
    </nav>
  )
}
