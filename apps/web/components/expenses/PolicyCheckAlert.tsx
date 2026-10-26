import { Alert } from "@/components/biz/Alert"
import type { PolicyCheckView } from "@/lib/expense"
import { formatFen } from "@/lib/format"

/** PolicyCheckAlert：展示 core 返回的制度校验结果（数字全部来自后端规则计算） */
export function PolicyCheckAlert({ check, checking }: { check: PolicyCheckView | null; checking?: boolean }) {
  if (!check) {
    return checking ? <Alert tone="info" title="正在校验报销制度…" /> : null
  }
  if (check.limit_per_person === 0 && !check.over) {
    // 实报实销的类型（交通、其他）或住宿信息还不全：给出说明，不显示「符合标准」
    return check.summary ? (
      <Alert tone="info" title="制度校验">
        {check.summary}
      </Alert>
    ) : null
  }
  const hasLimit = check.limit_per_person > 0
  const unit = check.unit === "night" ? "晚" : "人"
  const composed = hasLimit
    ? `标准 ${formatFen(check.limit_per_person)}/${unit}，本次 ${formatFen(check.per_person)}/${unit}`
    : `本次 ${formatFen(check.per_person)}`
  const overText = check.over ? `，超出 ${formatFen(check.over_amount)}` : ""
  const note = check.note ? `。${check.note}` : ""
  const text = check.summary ? `${check.summary}${note}` : `${composed}${overText}${note}`
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
