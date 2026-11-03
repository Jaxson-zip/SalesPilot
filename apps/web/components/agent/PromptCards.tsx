"use client"

import {
  Building2,
  ChartNoAxesColumn,
  ClipboardCheck,
  Cpu,
  GitBranch,
  Laptop,
  Package,
  Percent,
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
import { usePacks } from "@/hooks/useProductLines"
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
  [/卖什么|产品线/, Package],
  [/流程|阶段/, GitBranch],
  [/提成/, Percent],
  [/显存|GPU/, Cpu],
  [/设备|电脑/, Laptop],
  [/赢单要素/, Target],
  [/方案|报价/, Sparkles],
  [/报销/, Receipt],
  [/漏斗/, ChartNoAxesColumn],
  [/审批/, ClipboardCheck],
  [/下一步|提醒|任务/, ListTodo],
  [/跟进/, NotebookPen],
  [/制度|标准|招待/, ScrollText],
  [/商机|客户/, Building2],
]

/** packExample：当前行业包的出方案例句，替换标了 pack_example 的卡片，免得选了软件外包却示例大模型部署 */
export function promptCardsFrom(templates: PromptTemplate[], packExample?: string): PromptCard[] {
  return templates.map((t) => ({
    title: t.title,
    prompt: t.pack_example && packExample ? packExample : t.prompt,
    icon: ICON_RULES.find(([re]) => re.test(t.title))?.[1] ?? Sparkles,
  }))
}

/**
 * 欢迎页的示例问题：按角色来自 /api/templates（rules/templates.yaml），客户和商机按本人的数据填写，
 * 只放 AI 工具真正做得到的事（不放「算我这个月提成」这类没有数据来源的问题）。
 * learn：学习问答模式的引导问题，只放知识库和系统配置能回答的。
 */
export function PromptCards({
  onPick,
  learn,
  packId,
}: {
  onPick: (prompt: string) => void
  learn?: boolean
  /** 当前出方案用的行业包 */
  packId?: string | null
}) {
  const query = useTemplates({ fresh: true })
  const packs = usePacks()
  if (query.isPending) return <Skeleton className="mt-4 h-24 w-full" />
  const example = packs.data?.find((p) => p.id === packId)?.example_prompt
  const cards = promptCardsFrom((learn ? query.data?.learn_prompts : query.data?.ai_prompts) ?? [], example)
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
