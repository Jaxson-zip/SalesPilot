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
import { notifyError } from "@/hooks/notify"
import { api } from "@/lib/api"
import { downloadText } from "@/lib/download"
import { localDate } from "@/lib/format"
import { readStorage, writeStorage } from "@/lib/storage"

const today = () => localDate()

export type ExportEntity = "customers" | "opportunities" | "quotes" | "contracts" | "expenses"

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
  /** 导出前向服务端登记（按角色授权、限制条数、记入操作日志） */
  entity: ExportEntity
}): { rows: T[]; hidden: string[]; bar: ViewBarListProps; exportRows: (rows: T[]) => Promise<void> } {
  const { page, rows, filters, sort, csv, columns, exportName, entity } = opts
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

  /** 导出 CSV（ViewBar「导出 CSV」导出当前列表；批量栏「导出所选」导出勾选的行） */
  const exportRows = async (list: T[]) => {
    if (list.length === 0) return void toast("当前列表没有数据可导出")
    try {
      await api.post("/api/exports", { entity, rows: list.length })
    } catch (err) {
      return notifyError(err) // 无权导出或超过条数上限：服务端说明原因，并已记入操作日志
    }
    downloadText(toCsv(csv, list), `${exportName}-${today()}.csv`)
    toast.success(`已导出 ${list.length} 条（已记入操作日志）`)
  }

  const bar: ViewBarListProps = {
    filters,
    activeFilters: active,
    onFiltersChange: setActive,
    sort: sortKey,
    onSortChange: setSortKey,
    onExport: () => void exportRows(out),
    columns,
    hiddenColumns: hidden,
    onHiddenColumnsChange: (next) => {
      setHidden(next)
      writeStorage(storageKey, next.length ? JSON.stringify(next) : null)
    },
  }
  return { rows: out, hidden, bar, exportRows }
}
