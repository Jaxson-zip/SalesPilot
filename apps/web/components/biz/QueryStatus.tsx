import { ErrorState } from "@/components/biz/EmptyState"

/** 查询失败：错误码 + request_id + 重试 */
export function QueryError({
  error,
  onRetry,
  retrying,
}: {
  error: unknown
  onRetry: () => void
  retrying?: boolean
  /** 功能名（保留给调用方，错误文案统一由 ErrorState 给出） */
  feature?: string
}) {
  return <ErrorState error={error} onRetry={onRetry} retrying={retrying} />
}
