"use client"

import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import type { ViewBarListProps } from "@/components/biz/ViewBarMenus"
import {
  applyFilters,
  parseHiddenColumns,
  sortRows,
  toCsv,
  type ActiveFilters,
  type CsvColumn,
  type FilterDef,
  type SortAccessors,
  type SortKey,
} from "@/lib/list-view"
import { downloadText } from "@/lib/download"
import { localDate } from "@/lib/format"
import { readStorage, writeStorage } from "@/lib/storage"

const today = () => localDate()

/**
 * 列表视图状态：筛选 / 排序 / 导出 CSV / 显示字段（隐藏列记在 localStorage `sp.cols.<page>`）。
 * 返回过滤排序后的 rows 和传给 ViewBar 的 props。
 */
export function useListView<T>(opts: {
  page: string
  rows: T[]
  filters: FilterDef<T>[]
  sort: SortAccessors<T>
  csv: CsvColumn<T>[]
  /** 可在「显示字段」里隐藏的列 */
  columns?: { id: string; label: string }[]
  exportName: string
}): { rows: T[]; hidden: string[]; bar: ViewBarListProps } {
  const { page, rows, filters, sort, csv, columns, exportName } = opts
  const [active, setActive] = useState<ActiveFilters>({})
  const [sortKey, setSortKey] = useState<SortKey>("default")
  const [hidden, setHidden] = useState<string[]>([])
  const storageKey = `sp.cols.${page}`

  // 只在客户端读取偏好（SSR 时没有 localStorage）
  useEffect(() => setHidden(parseHiddenColumns(readStorage(storageKey))), [storageKey])

  const out = useMemo(
    () => sortRows(applyFilters(rows, filters, active), sortKey, sort),
    [rows, filters, active, sortKey, sort],
  )

  const bar: ViewBarListProps = {
    filters,
    activeFilters: active,
    onFiltersChange: setActive,
    sort: sortKey,
    onSortChange: setSortKey,
    onExport: () => {
      if (out.length === 0) return void toast("当前列表没有数据可导出")
      downloadText(toCsv(csv, out), `${exportName}-${today()}.csv`)
      toast.success(`已导出 ${out.length} 条`)
    },
    columns,
    hiddenColumns: hidden,
    onHiddenColumnsChange: (next) => {
      setHidden(next)
      writeStorage(storageKey, next.length ? JSON.stringify(next) : null)
    },
  }
  return { rows: out, hidden, bar }
}
