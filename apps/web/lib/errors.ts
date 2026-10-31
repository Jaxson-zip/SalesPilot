/** 错误码 → 用户可读的中文提示（toast / 错误状态共用，纯函数便于测试） */
import { isApiError, type ApiError } from "@/lib/api"
import { ErrorCode } from "@/types/api"

/** 42201 时 data.rule 的中文说明（契约 §2–§6） */
const RULE_MESSAGES: Record<string, string> = {
  opportunity_stage_final: "商机已是赢单 / 输单终态，不能再切换阶段",
  quote_status_transition: "报价单当前状态不允许该操作，请刷新后重试",
  payment_exceeds_balance: "回款金额超过未回款余额",
  expense_missing_invoice: "票据不全：客户招待需要发票和小票，其他类型至少一张发票",
  approval_already_decided: "该审批已被处理，请刷新列表",
}

/** 40301 时 data.rule 的中文说明（契约 §0） */
const FORBIDDEN_MESSAGES: Record<string, string> = {
  role_forbidden: "当前角色无权执行该操作（管理员负责系统配置，业务数据只读）",
  not_owner: "只有负责人本人可以修改这条记录",
}

function ruleOf(data: unknown): string | null {
  if (typeof data === "object" && data !== null && "rule" in data) {
    const rule = (data as { rule: unknown }).rule
    return typeof rule === "string" ? rule : null
  }
  return null
}

/**
 * 服务端没有这个接口：HTTP 501，或路由不存在（FastAPI 默认 404，message 为 "Not Found"，
 * 与业务 40401「记录不存在」的中文消息区分）。多半是前后端版本不一致。
 */
function isMissingRoute(err: ApiError): boolean {
  return (
    err.status === 501 || err.code === ErrorCode.NOT_IMPLEMENTED || (err.status === 404 && err.message === "Not Found")
  )
}

/** 写操作失败时的中文提示 */
export function errorMessage(err: unknown): string {
  if (!isApiError(err)) return err instanceof Error ? err.message : "操作失败，请稍后重试"
  if (isMissingRoute(err)) return "服务端暂不支持这个操作，请刷新页面；仍不行请联系管理员更新服务"
  switch (err.code) {
    case ErrorCode.BIZ_RULE: {
      const rule = ruleOf(err.data)
      return (rule && RULE_MESSAGES[rule]) || err.message || "业务规则不满足"
    }
    case ErrorCode.FORBIDDEN: {
      const rule = ruleOf(err.data)
      if (rule === "privacy") return err.message // 数据安全限制：服务端给出具体原因（如「当前角色不能导出客户」）
      return (rule && FORBIDDEN_MESSAGES[rule]) || "当前角色无权执行该操作"
    }
    case ErrorCode.DUPLICATE:
      return "请勿重复提交，该单据已提交过"
    case ErrorCode.NOT_FOUND:
      return "记录不存在或你无权查看"
    case ErrorCode.VALIDATION:
      return err.message ? `参数校验失败：${err.message}` : "参数校验失败"
    default:
      return err.message || "操作失败，请稍后重试"
  }
}

/** toast 副标题：错误码 + request_id，方便排查 */
export function errorMeta(err: unknown): string | undefined {
  if (!isApiError(err)) return undefined
  return [`错误码 ${err.code}`, err.requestId].filter(Boolean).join(" · ")
}
