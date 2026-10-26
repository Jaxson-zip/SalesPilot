import { Alert } from "@/components/biz/Alert"
import type { PolicyCheckView } from "@/lib/expense"
import { formatFen } from "@/lib/format"

/** PolicyCheckAlert：展示 core 返回的制度校验结果（数字全部来自后端规则计算） */
export function PolicyCheckAlert({ check, checking }: { check: PolicyCheckView | null; checking?: boolean }) {
  if (!check) {
    return checking ? <Alert tone="info" title="正在校验报销制度…" /> : null
  }
  const hasLimit = check.limit_per_person > 0
  const composed = hasLimit
    ? `标准 ${formatFen(check.limit_per_person)}/人，本次 ${formatFen(check.per_person)}/人`
    : `本次 ${formatFen(check.per_person)}/人`
  const overText = check.over ? `，超出 ${formatFen(check.over_amount)}` : ""
  const text = check.summary ?? `${composed}${overText}${check.note ? `。${check.note}` : ""}`
  if (check.over) {
    return (
      <Alert tone="warn" title="超出报销标准，需主管审批">
        {text}
      </Alert>
    )
  }
  return (
    <Alert tone="ok" title="符合报销标准">
      {text}
    </Alert>
  )
}
