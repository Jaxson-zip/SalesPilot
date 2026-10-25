import type { ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

/** Twenty 风格浅底标签，8 种颜色（状态、行业、等级） */
export const TAG_COLORS = {
  gray: "bg-zinc-100 text-zinc-700",
  blue: "bg-blue-100 text-blue-700",
  green: "bg-emerald-100 text-emerald-700",
  orange: "bg-orange-100 text-orange-700",
  red: "bg-red-100 text-red-700",
  purple: "bg-violet-100 text-violet-700",
  yellow: "bg-amber-100 text-amber-800",
  sky: "bg-sky-100 text-sky-700",
} as const

export type TagColor = keyof typeof TAG_COLORS

const HASH_ORDER: TagColor[] = ["purple", "orange", "sky", "green", "blue", "yellow", "red", "gray"]

/** 没有固定映射的取值（例如行业）按文字稳定地分配颜色 */
export function colorFor(text: string): TagColor {
  let h = 0
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return HASH_ORDER[h % HASH_ORDER.length]
}

export function Tag({
  children,
  color = "gray",
  className,
}: {
  children: ReactNode
  color?: TagColor
  className?: string
}) {
  return (
    <Badge className={cn("h-5 rounded px-1.5 text-xs font-normal", TAG_COLORS[color], className)}>{children}</Badge>
  )
}
