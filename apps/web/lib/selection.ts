/** 表格多选的纯函数：选中行、批量栏文案 */

/** 选中状态：行 id → true（与 TanStack Table 的 RowSelectionState 结构一致） */
export type SelectionState = Record<string, boolean>

/**
 * 从当前可见的行里取出被选中的行（按行的顺序）。
 * 切换视图 / 筛选后，看不到的行即使还在 state 里也不算选中，避免对看不到的数据做批量操作。
 */
export function pickSelected<T>(rows: T[], selection: SelectionState, getId: (row: T) => string): T[] {
  return rows.filter((r) => selection[getId(r)] === true)
}

/** 批量栏左侧文案 */
export function selectionLabel(count: number): string {
  return `已选 ${count} 条`
}

/** 只保留当前可见行的选中状态（用于批量操作完成后或数据刷新后清理） */
export function pruneSelection<T>(rows: T[], selection: SelectionState, getId: (row: T) => string): SelectionState {
  const out: SelectionState = {}
  for (const r of rows) {
    const id = getId(r)
    if (selection[id]) out[id] = true
  }
  return out
}
