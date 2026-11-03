/** 工作台待办里除任务以外的事项（GET /api/dashboard/todos）的纯函数：类型文案、计数 */
import type { TodoItem, TodoKind } from "@/types/api"

export const TODO_KIND_LABEL: Record<TodoKind, string> = {
  payment_overdue: "回款",
  payment_due: "回款",
  report: "日报",
  approval: "审批",
}

/** 右侧的时间说明：逾期回款「已逾期」，其余「今天」；待审批没有到期日不显示 */
export function todoWhen(t: Pick<TodoItem, "kind" | "overdue">): string {
  if (t.overdue) return "已逾期"
  return t.kind === "approval" ? "" : "今天"
}

/** 计入「今天 N 项待办，M 项已逾期」的数量 */
export function todoCounts(items: Pick<TodoItem, "overdue">[]): { today: number; overdue: number } {
  const overdue = items.filter((t) => t.overdue).length
  return { today: items.length - overdue, overdue }
}
