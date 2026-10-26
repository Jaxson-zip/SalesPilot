"use client"

import {
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
  type Table,
} from "@tanstack/react-table"
import { Plus, type LucideIcon } from "lucide-react"
import { useMemo, useState, type ReactNode } from "react"

import { Checkbox } from "@/components/ui/checkbox"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

export interface GridColumn<T> {
  id: string
  label: string
  icon: LucideIcon
  cell: (row: T) => ReactNode
  /** 数字列：右对齐 + tabular-nums */
  align?: "right"
  /** 次要列（原型里的 `lg`）：<1024 隐藏 */
  secondary?: boolean
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
}

const hideSecondary = (c: { secondary?: boolean }) => (c.secondary ? "hidden lg:table-cell" : "")
const SKELETON_ROWS = Array.from({ length: 8 }, (_, i) => i)

/**
 * DataGrid：Twenty 网格。表头 32px、行高 34px、竖向分隔线、首列勾选、末行「+ 新增一条」。
 * 不允许横向滚动：table-fixed + 单元格截断；<1024 隐藏次要列；<768 改为卡片列表。
 */
export function DataGrid<T>({ columns, data, getRowId, loading, total, onAddRow, empty }: DataGridProps<T>) {
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const defs = useMemo<ColumnDef<T>[]>(
    () => columns.map((c) => ({ id: c.id, header: c.label, cell: ({ row }) => c.cell(row.original) })),
    [columns],
  )
  const table = useReactTable({
    data,
    columns: defs,
    getRowId,
    state: { rowSelection },
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
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
              <GridHead table={table} columns={columns} />
              <GridBody table={table} columns={columns} loading={loading} onAddRow={onAddRow} />
            </table>
          </div>
          <GridCards columns={columns} data={data} getRowId={getRowId} loading={loading} />
        </>
      )}
      <div className="flex h-8 shrink-0 items-center justify-between border-t border-zinc-200 px-3 text-xs text-zinc-500">
        <span>{loading ? "加载中…" : `共 ${total ?? data.length} 条`}</span>
        <span className="max-md:hidden">已选 {Object.keys(rowSelection).length} 条</span>
      </div>
    </>
  )
}

function GridHead<T>({ table, columns }: { table: Table<T>; columns: GridColumn<T>[] }) {
  const all = table.getIsAllRowsSelected() ? true : table.getIsSomeRowsSelected() ? "indeterminate" : false
  return (
    <thead className="sticky top-0 z-10 bg-white">
      <tr className="h-8 text-zinc-500">
        <th className="w-9 border-b border-zinc-200">
          <Checkbox aria-label="全选" checked={all} onCheckedChange={(v) => table.toggleAllRowsSelected(v === true)} />
        </th>
        {columns.map((c) => (
          <th
            key={c.id}
            className={cn(
              "overflow-hidden border-r border-b border-zinc-200 px-2 text-left font-normal whitespace-nowrap",
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
        {/* 末列留白（原型里的「+ 字段」入口；显示字段在 ViewBar「选项 → 显示字段」里设置） */}
        <th className="w-8 border-b border-zinc-200" aria-hidden />
      </tr>
    </thead>
  )
}

function GridBody<T>({
  table,
  columns,
  loading,
  onAddRow,
}: {
  table: Table<T>
  columns: GridColumn<T>[]
  loading?: boolean
  onAddRow?: () => void
}) {
  const cellBase = "overflow-hidden border-r border-b border-zinc-100 px-2 whitespace-nowrap"
  if (loading) {
    return (
      <tbody>
        {SKELETON_ROWS.map((i) => (
          <tr key={i} className="h-[34px]">
            <td className="border-b border-zinc-100" />
            {columns.map((c) => (
              <td key={c.id} className={cn(cellBase, hideSecondary(c))}>
                <Skeleton className="h-3.5 w-3/4" />
              </td>
            ))}
            <td className="border-b border-zinc-100" />
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
          className="h-[34px] hover:bg-zinc-50"
          data-state={row.getIsSelected() ? "selected" : undefined}
        >
          <td className="border-b border-zinc-100 text-center">
            <Checkbox
              aria-label="选择"
              checked={row.getIsSelected()}
              onCheckedChange={(v) => row.toggleSelected(v === true)}
            />
          </td>
          {columns.map((c) => (
            <td key={c.id} className={cn(cellBase, hideSecondary(c), c.align === "right" && "text-right tabular-nums")}>
              <div className="truncate">{c.cell(row.original)}</div>
            </td>
          ))}
          <td className="border-b border-zinc-100" />
        </tr>
      ))}
      {onAddRow ? (
        <tr className="h-[34px] text-zinc-400">
          <td className="border-b border-zinc-100" />
          <td colSpan={columns.length + 1} className="border-b border-zinc-100 px-2">
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
