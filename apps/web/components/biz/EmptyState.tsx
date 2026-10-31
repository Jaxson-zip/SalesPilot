import { CircleAlert, Inbox, Lock, RotateCw, type LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { isApiError } from "@/lib/api"

/** 通用空状态：图标 + 标题 + 说明 + 可选操作 */
export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
}: {
  icon?: LucideIcon
  title: string
  description?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 py-12 text-center text-zinc-500">
      <Icon className="size-8 text-zinc-300" />
      <div className="mt-2 font-medium text-zinc-700">{title}</div>
      {description ? <div className="mt-1 max-w-sm">{description}</div> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}

/** 加载失败：显示错误码、request_id 和重试按钮 */
export function ErrorState({ error, onRetry, retrying }: { error: unknown; onRetry: () => void; retrying?: boolean }) {
  const message = error instanceof Error ? error.message : "加载失败"
  const meta = isApiError(error) ? [`错误码 ${error.code}`, error.requestId].filter(Boolean).join(" · ") : null
  return (
    <EmptyState
      icon={CircleAlert}
      title="数据加载失败"
      description={
        <>
          <div>{message}</div>
          {meta ? <div className="mt-1 text-xs text-zinc-400">{meta}</div> : null}
        </>
      }
      action={
        <Button variant="outline" size="sm" onClick={onRetry} disabled={retrying}>
          <RotateCw className={retrying ? "animate-spin" : undefined} />
          重试
        </Button>
      }
    />
  )
}

/** 当前角色无权查看 */
export function Locked({ description }: { description: string }) {
  return <EmptyState icon={Lock} title="无权访问" description={description} />
}
