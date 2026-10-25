import { Sparkles, type LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

const AVATAR_COLORS = [
  "bg-sky-100 text-sky-700",
  "bg-pink-100 text-pink-700",
  "bg-amber-100 text-amber-700",
  "bg-emerald-100 text-emerald-700",
  "bg-indigo-100 text-indigo-700",
  "bg-orange-100 text-orange-700",
]

function avatarColor(name: string): string {
  const code = name.codePointAt(0) ?? 0
  return AVATAR_COLORS[code % AVATAR_COLORS.length]
}

/** 首字头像；name 为 "AI" 时显示 AI 图标（violet） */
export function LetterAvatar({ name, className }: { name: string; className?: string }) {
  const isAi = name === "AI"
  return (
    <span
      className={cn(
        "inline-flex size-4 shrink-0 items-center justify-center rounded-full text-[9px] font-medium",
        isAi ? "text-ai bg-violet-100" : avatarColor(name),
        className,
      )}
    >
      {isAi ? <Sparkles className="size-2.5" /> : name.slice(0, 1)}
    </span>
  )
}

/** Chip：关联对象（头像 / 图标 / logo + 名称），用于客户、人员 */
export function Chip({
  name,
  logo,
  icon: Icon,
  className,
}: {
  name: string
  /** 客户 logo 字（方形白底） */
  logo?: string
  icon?: LucideIcon
  className?: string
}) {
  let lead: ReactNode
  if (logo) {
    lead = (
      <span className="inline-flex size-4 items-center justify-center rounded-sm border border-zinc-200 bg-white text-[9px] font-semibold">
        {logo}
      </span>
    )
  } else if (Icon) {
    lead = (
      <span className="inline-flex size-4 items-center justify-center text-zinc-500">
        <Icon className="size-3" />
      </span>
    )
  } else {
    lead = <LetterAvatar name={name} />
  }
  return (
    <span
      className={cn(
        "inline-flex h-5 max-w-full min-w-0 items-center gap-1 rounded bg-zinc-100 pr-1.5 pl-0.5 whitespace-nowrap text-zinc-700",
        className,
      )}
      title={name}
    >
      {lead}
      <span className="truncate">{name}</span>
    </span>
  )
}

/** 网址等外链的圆角描边标签 */
export function LinkChip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex h-5 max-w-full items-center truncate rounded-full border border-zinc-200 px-2 whitespace-nowrap text-zinc-600">
      {children}
    </span>
  )
}
