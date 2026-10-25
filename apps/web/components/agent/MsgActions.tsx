"use client"

import { Copy, RefreshCw, ThumbsDown, ThumbsUp, type LucideIcon } from "lucide-react"
import { toast } from "sonner"

/** 消息操作：复制、重新生成、点赞、点踩 */
export function MsgActions({ text, onRegenerate }: { text: string; onRegenerate?: () => void }) {
  const copy = () => {
    navigator.clipboard
      .writeText(text)
      .then(() => toast.success("已复制"))
      .catch(() => toast.error("复制失败"))
  }
  const items: { icon: LucideIcon; title: string; onClick: () => void }[] = [
    { icon: Copy, title: "复制", onClick: copy },
    { icon: RefreshCw, title: "重新生成", onClick: () => onRegenerate?.() },
    { icon: ThumbsUp, title: "有帮助", onClick: () => toast("感谢反馈") },
    { icon: ThumbsDown, title: "没帮助", onClick: () => toast("感谢反馈，我们会改进") },
  ]
  return (
    <div className="-ml-1.5 flex items-center gap-0.5 text-zinc-400">
      {items.map(({ icon: Icon, title, onClick }) => (
        <button
          key={title}
          type="button"
          title={title}
          onClick={onClick}
          className="inline-flex size-7 items-center justify-center rounded-md hover:bg-zinc-100 hover:text-zinc-700"
        >
          <Icon className="size-3.5" />
        </button>
      ))}
    </div>
  )
}
