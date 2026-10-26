import { Construction } from "lucide-react"

import { EmptyState, ErrorState } from "@/components/biz/EmptyState"
import { isNotImplemented } from "@/lib/errors"

/** 接口已占位但未实现（501 / 50101）：显示「后端开发中」而不是报错 */
export function BackendPending({ feature }: { feature?: string }) {
  return (
    <EmptyState
      icon={Construction}
      title="后端开发中"
      description={`${feature ? `${feature}接口` : "该接口"}还在开发，页面已按原型完成，接口就绪后自动显示数据。`}
    />
  )
}

/** 查询失败：未实现 → 后端开发中；其他 → 错误码 + request_id + 重试 */
export function QueryError({
  error,
  onRetry,
  retrying,
  feature,
}: {
  error: unknown
  onRetry: () => void
  retrying?: boolean
  feature?: string
}) {
  if (isNotImplemented(error)) return <BackendPending feature={feature} />
  return <ErrorState error={error} onRetry={onRetry} retrying={retrying} />
}
