"use client"

import { useCallback, useMemo, useState } from "react"

import { pickSelected, type SelectionState } from "@/lib/selection"

/** 列表多选状态：selection 传给 DataGrid；selected 是当前可见且被选中的行 */
export function useRowSelection<T>(rows: T[], getId: (row: T) => string) {
  const [selection, setSelection] = useState<SelectionState>({})
  const selected = useMemo(() => pickSelected(rows, selection, getId), [rows, selection, getId])
  const clear = useCallback(() => setSelection({}), [])
  return { selection, setSelection, selected, count: selected.length, clear }
}
