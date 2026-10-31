import type { AgentArtifact } from "@/lib/agent-reducer"

/** 确认后写操作的执行结果（core 的 artifact{type: action_result}）：界面按它显示，不看模型怎么说 */
export interface ActionResult {
  action: string
  status: "done" | "failed" | "cancelled"
  summary: string
  /** 写入后的记录入口（前端路由） */
  href: string | null
}

export function isActionResult(v: unknown): v is ActionResult {
  if (typeof v !== "object" || v === null) return false
  const r = v as Record<string, unknown>
  return (
    typeof r.action === "string" &&
    (r.status === "done" || r.status === "failed" || r.status === "cancelled") &&
    typeof r.summary === "string"
  )
}

/** 本条回复里的执行结果（同一条回复只确认一次，取最新一份） */
export function actionResultOf(artifacts: AgentArtifact[]): ActionResult | null {
  const a = [...artifacts].reverse().find((x) => x.type === "action_result")
  return a && isActionResult(a.data) ? a.data : null
}
