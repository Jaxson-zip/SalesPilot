import { Building2, ChartNoAxesColumn, FileText, Receipt, Sparkles, Wallet, type LucideIcon } from "lucide-react"

export interface PromptCard {
  icon: LucideIcon
  title: string
  prompt: string
}

export const DEFAULT_PROMPTS: PromptCard[] = [
  {
    icon: Sparkles,
    title: "出部署方案",
    prompt: "给深圳明理律所出一份私有化部署方案：Qwen3-32B，50 人并发，做合同审查，预算 40 万以内",
  },
  { icon: Receipt, title: "报销", prompt: "昨天请明理律所王律师他们 4 个人吃饭，花了 860，帮我报销" },
  { icon: ChartNoAxesColumn, title: "漏斗分析", prompt: "本月销售漏斗怎么样？哪些商机有风险" },
  { icon: Wallet, title: "算提成", prompt: "我这个月的提成大概多少" },
]

/** 只读角色（管理员）：只给查询类提示，AI 写操作工具不可用（契约 §0） */
export const QUERY_PROMPTS: PromptCard[] = [
  { icon: ChartNoAxesColumn, title: "漏斗分析", prompt: "本月全公司销售漏斗怎么样？哪些商机有风险" },
  { icon: Wallet, title: "提成汇总", prompt: "本月各销售的预估提成和已确认提成分别是多少" },
  { icon: FileText, title: "报价概况", prompt: "最近有哪些报价单在等主管审批？毛利率分别多少" },
  { icon: Building2, title: "客户跟进", prompt: "哪些客户超过两周没有跟进了" },
]

/** 欢迎页 4 张快捷提示卡片 */
export function PromptCards({
  prompts = DEFAULT_PROMPTS,
  onPick,
}: {
  prompts?: PromptCard[]
  onPick: (prompt: string) => void
}) {
  return (
    <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
      {prompts.map((p) => (
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
