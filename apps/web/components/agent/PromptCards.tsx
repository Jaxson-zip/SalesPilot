"use client"

import {
  Building2,
  ChartNoAxesColumn,
  ClipboardCheck,
  ListTodo,
  NotebookPen,
  Receipt,
  ScrollText,
  Sparkles,
  Swords,
  Target,
  type LucideIcon,
} from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import { useTemplates } from "@/hooks/useTemplates"
import type { PromptTemplate } from "@/types/api"

export interface PromptCard {
  icon: LucideIcon
  title: string
  prompt: string
}

/** 按标题关键词配图标；没匹配上用通用图标 */
const ICON_RULES: [RegExp, LucideIcon][] = [
  [/竞品/, Swords],
  [/赢单要素/, Target],
  [/方案|报价/, Sparkles],
  [/报销/, Receipt],
  [/漏斗/, ChartNoAxesColumn],
  [/审批/, ClipboardCheck],
  [/下一步|提醒|任务/, ListTodo],
  [/跟进/, NotebookPen],
  [/制度|标准/, ScrollText],
  [/商机|客户/, Building2],
]

export function promptCardsFrom(templates: PromptTemplate[]): PromptCard[] {
  return templates.map((t) => ({
    ...t,
    icon: ICON_RULES.find(([re]) => re.test(t.title))?.[1] ?? Sparkles,
  }))
}

/**
 * 欢迎页的示例问题：按角色来自 /api/templates（rules/templates.yaml），
 * 只放 AI 工具真正做得到的事（不放「算我这个月提成」这类没有数据来源的问题）。
 */
export function PromptCards({ onPick }: { onPick: (prompt: string) => void }) {
  const query = useTemplates()
  if (query.isPending) return <Skeleton className="mt-4 h-24 w-full" />
  const cards = promptCardsFrom(query.data?.ai_prompts ?? [])
  return (
    <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
      {cards.map((p) => (
        <button
          key={p.title}
          type="button"
          onClick={() => onPick(p.prompt)}
          className="flex min-w-0 gap-3 rounded-xl border border-zinc-200 p-3.5 text-left hover:border-zinc-300 hover:bg-zinc-50"
        >
          <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-zinc-100">
            <p.icon className="size-4 text-zinc-600" />
          </span>
          <div className="min-w-0">
            <div className="font-medium">{p.title}</div>
            <div className="mt-0.5 line-clamp-2 text-zinc-500">{p.prompt}</div>
          </div>
        </button>
      ))}
    </div>
  )
}
