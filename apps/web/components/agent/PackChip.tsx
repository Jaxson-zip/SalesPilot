"use client"

import { Boxes, Lock } from "lucide-react"

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { usePacks } from "@/hooks/useProductLines"

/** 行业包只读标签：从商机进入时按商机产品线匹配，锁定不能切换 */
export function PackChip({ pack }: { pack: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex h-8 min-w-0 cursor-help items-center gap-1.5 rounded-full bg-zinc-100 px-3 text-xs text-zinc-600 max-sm:shrink-0 max-sm:px-2.5">
          <Boxes className="size-3.5 shrink-0" />
          <span className="truncate max-sm:overflow-visible">
            {pack}
            <span className="max-sm:hidden"> · 按商机产品线自动匹配</span>
          </span>
          <Lock className="size-3 shrink-0 text-zinc-400 max-sm:hidden" />
        </span>
      </TooltipTrigger>
      <TooltipContent>这条对话关联了商机，行业包按商机的产品线自动匹配</TooltipContent>
    </Tooltip>
  )
}

/** 没关联商机时选行业包：AI 按选的行业查资料、出方案（默认是团队默认产品线的行业包） */
export function PackSelect({ value, onChange }: { value: string; onChange: (pack: string) => void }) {
  const { data } = usePacks()
  const packs = data ?? []
  const current = packs.find((p) => p.id === value)
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger
        size="sm"
        aria-label="选择行业包"
        title="这次对话按哪个行业出方案、查资料"
        className="h-8 min-w-0 gap-1.5 rounded-full border-zinc-200 px-3 text-xs text-zinc-700 shadow-none hover:bg-zinc-50"
      >
        <Boxes className="size-3.5 shrink-0 text-zinc-500" />
        <SelectValue>{current?.name ?? value}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {packs.map((p) => (
          <SelectItem key={p.id} value={p.id}>
            {p.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
