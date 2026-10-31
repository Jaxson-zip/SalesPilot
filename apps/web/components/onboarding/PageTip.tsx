"use client"

import { Lightbulb, X } from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { useDismissed } from "@/hooks/useDismissed"
import { tipKey } from "@/lib/onboarding"
import { cn } from "@/lib/utils"

/** 页面第一次打开时的一条提示：说清楚这页怎么用，关掉后这台电脑上不再出现 */
export function PageTip({ id, children, className }: { id: string; children: ReactNode; className?: string }) {
  const [dismissed, dismiss] = useDismissed(tipKey(id))
  if (dismissed !== false) return null
  return (
    <div
      role="note"
      className={cn(
        "flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900",
        className,
      )}
    >
      <Lightbulb className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1 text-xs leading-5">{children}</div>
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label="知道了，不再提示"
        title="知道了"
        onClick={dismiss}
        className="-mr-1 text-amber-900"
      >
        <X />
      </Button>
    </div>
  )
}
