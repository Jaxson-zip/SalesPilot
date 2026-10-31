"use client"

import { Check, Copy, RefreshCw, ThumbsDown, ThumbsUp, type LucideIcon } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import type { Rating } from "@/hooks/useAiFeedback"
import { copyText } from "@/lib/clipboard"
import { cn } from "@/lib/utils"

export interface MsgFeedback {
  rating: Rating | null
  /** rating 为 null：取消；comment：点踩时写的原因（可不填） */
  onRate: (rating: Rating | null, comment?: string) => void
}

/** 消息操作：复制、重新生成、点赞、点踩（评价存到服务器，主管 / 管理员在「AI 用量」里看没帮助的回复） */
export function MsgActions({
  text,
  onRegenerate,
  feedback,
}: {
  text: string
  onRegenerate?: () => void
  /** 会话还没有 id 时不显示点赞点踩 */
  feedback?: MsgFeedback
}) {
  const [copied, setCopied] = useState(false)
  const [asking, setAsking] = useState(false)
  const [reason, setReason] = useState("")
  const rating = feedback?.rating ?? null

  const copy = async () => {
    if (!(await copyText(text))) {
      toast.error("复制失败，请手动选中文字复制")
      return
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
    toast.success("已复制")
  }
  // 再点一次同一个取消；点踩后可以补一句原因
  const rate = (r: Rating) => {
    if (!feedback) return
    if (rating === r) {
      feedback.onRate(null)
      setAsking(false)
      return
    }
    feedback.onRate(r)
    setAsking(r === "down")
    setReason("")
    if (r === "up") toast("感谢反馈")
  }
  const sendReason = () => {
    if (reason.trim()) feedback?.onRate("down", reason.trim())
    setAsking(false)
    toast("感谢反馈，我们会改进")
  }

  const items: { icon: LucideIcon; title: string; onClick: () => void; active?: boolean }[] = [
    { icon: copied ? Check : Copy, title: "复制", onClick: () => void copy() },
    // 没有处理函数（历史消息）时不显示「重新生成」
    ...(onRegenerate ? [{ icon: RefreshCw, title: "重新生成", onClick: onRegenerate }] : []),
    ...(feedback
      ? [
          { icon: ThumbsUp, title: "有帮助", onClick: () => rate("up"), active: rating === "up" },
          { icon: ThumbsDown, title: "没帮助", onClick: () => rate("down"), active: rating === "down" },
        ]
      : []),
  ]
  return (
    <div className="space-y-2">
      <div className="-ml-1.5 flex items-center gap-0.5 text-zinc-400">
        {items.map(({ icon: Icon, title, onClick, active }) => (
          <button
            key={title}
            type="button"
            title={title}
            aria-label={title}
            aria-pressed={active}
            onClick={onClick}
            className={cn(
              "inline-flex size-7 items-center justify-center rounded-md hover:bg-zinc-100 hover:text-zinc-700",
              active && "text-zinc-900",
            )}
          >
            <Icon className={cn("size-3.5", active && "fill-current")} />
          </button>
        ))}
      </div>
      {asking ? (
        <form
          className="flex max-w-md items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            sendReason()
          }}
        >
          <input
            autoFocus
            value={reason}
            maxLength={500}
            onChange={(e) => setReason(e.target.value)}
            placeholder="哪里不对？如价格算错、没答到点上（可不填）"
            aria-label="没帮助的原因"
            className="h-8 min-w-0 flex-1 rounded-md border border-zinc-200 px-2.5 text-xs outline-none focus:border-zinc-400"
          />
          <button
            type="submit"
            className="h-8 shrink-0 rounded-md bg-zinc-900 px-3 text-xs text-white hover:bg-zinc-700"
          >
            提交
          </button>
          <button
            type="button"
            onClick={() => setAsking(false)}
            className="h-8 shrink-0 px-1 text-xs text-zinc-400 hover:text-zinc-700"
          >
            不填了
          </button>
        </form>
      ) : null}
    </div>
  )
}
