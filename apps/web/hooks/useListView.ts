"use client"

import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import type { ViewBarListProps } from "@/components/biz/ViewBarMenus"
import {
  applyFilters,
  filterParams,
  parseHiddenColumns,
  sortRows,
  toCsv,
  type ActiveFilters,
  type CsvColumn,
  type FilterDef,
  type ServerListParams,
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

/** 服务端分页：筛选 / 排序交给接口，导出时按当前条件取全部页 */
export interface ServerMode<T> {
  /** 当前条件下的总条数（接口返回的 total；导出时才读取，所以列表查询可以写在 useListView 之后） */
  total: () => number | undefined
  /** 取当前条件下的全部行（导出用；条数已在导出登记时校验过上限） */
  fetchAll: (params: ServerListParams) => Promise<T[]>
}

/**
 * 列表视图状态：筛选 / 排序 / 导出 CSV / 显示字段（隐藏列记在 localStorage `sp.cols.<page>`）。
 * 前端模式返回过滤排序后的 rows；服务端模式（server）rows 原样返回，筛选 / 排序 / 页码由 params、page
 * 交给列表接口，改筛选或排序时回到第 1 页。
 */
export function useListView<T>(opts: {
  page: string
  rows: T[]
  filters: FilterDef<T>[]
  /** 前端排序取值；服务端模式不需要 */
  sort?: SortAccessors<T>
  csv: CsvColumn<T>[]
  /** 可在「显示字段」里隐藏的列 */
  columns?: { id: string; label: string }[]
  exportName: string
  /** 导出前向服务端登记（按角色授权、限制条数、记入操作日志） */
  entity: ExportEntity
  server?: ServerMode<T>
}): {
  rows: T[]
  hidden: string[]
  bar: ViewBarListProps
  exportRows: (rows: T[]) => Promise<void>
  /** 服务端模式：传给列表接口的筛选 / 排序 */
  params: ServerListParams
  /** 当前页码（从 1 开始） */
  pageNo: number
  setPageNo: (n: number) => void
} {
  const { page, rows, filters, sort, csv, columns, exportName, entity, server } = opts
  const [active, setActive] = useState<ActiveFilters>({})
  const [sortKey, setSortKey] = useState<SortKey>("default")
  const [pageNo, setPageNo] = useState(1)
  const [hidden, setHidden] = useState<string[]>([])
  const storageKey = `sp.cols.${page}`

  // 只在客户端读取偏好（SSR 时没有 localStorage）
  useEffect(() => setHidden(parseHiddenColumns(readStorage(storageKey))), [storageKey])

  const out = useMemo(
    () => (server || !sort ? rows : sortRows(applyFilters(rows, filters, active), sortKey, sort)),
    [server, rows, filters, active, sortKey, sort],
  )
  const params = useMemo<ServerListParams>(
    () => ({ sort: sortKey, filters: filterParams(filters, active) }),
    [filters, active, sortKey],
  )

  /** 导出前向服务端登记（无权导出或超过条数上限时拒绝，并已记入操作日志） */
  const register = async (count: number) => {
    if (count === 0) {
      toast("当前列表没有数据可导出")
      return false
    }
    try {
      await api.post("/api/exports", { entity, rows: count })
      return true
    } catch (err) {
      notifyError(err)
      return false
    }
  }
  const download = (list: T[]) => {
    downloadText(toCsv(csv, list), `${exportName}-${today()}.csv`)
    toast.success(`已导出 ${list.length} 条（已记入操作日志）`)
  }

  /** 导出 CSV（批量栏「导出所选」导出勾选的行） */
  const exportRows = async (list: T[]) => {
    if (await register(list.length)) download(list)
  }
  /** ViewBar「导出 CSV」：导出当前条件下的全部行（服务端模式要取全部页） */
  const exportAll = async () => {
    if (!server) return exportRows(out)
    if (!(await register(server.total() ?? 0))) return
    try {
      download(await server.fetchAll(params))
    } catch (err) {
      notifyError(err)
    }
  }

  const bar: ViewBarListProps = {
    filters,
    activeFilters: active,
    onFiltersChange: (next) => {
      setActive(next)
      setPageNo(1)
    },
    sort: sortKey,
    onSortChange: (next) => {
      setSortKey(next)
      setPageNo(1)
    },
    onExport: () => void exportAll(),
    columns,
    hiddenColumns: hidden,
    onHiddenColumnsChange: (next) => {
      setHidden(next)
      writeStorage(storageKey, next.length ? JSON.stringify(next) : null)
    },
  }
  return { rows: out, hidden, bar, exportRows, params, pageNo, setPageNo }
}
