"use client"

import { BookOpen, RotateCcw } from "lucide-react"
import type { ReactNode } from "react"
import { toast } from "sonner"

import { FrameAction, PageFrame } from "@/components/biz/PageFrame"
import { Tag } from "@/components/biz/Tag"
import { useSession } from "@/components/shell/SessionProvider"
import { Skeleton } from "@/components/ui/skeleton"
import { useTemplates } from "@/hooks/useTemplates"
import { AI_CAN, AI_CANNOT, EXPENSE_FLOW, FAQ, QUICK_START, STAGE_GUIDE } from "@/lib/help-content"
import { STAGE_META } from "@/lib/labels"
import { guideKeys } from "@/lib/onboarding"
import { writeStorage } from "@/lib/storage"

const SECTIONS = [
  { id: "start", label: "快速上手" },
  { id: "stages", label: "商机阶段" },
  { id: "expense", label: "报销说明" },
  { id: "ai", label: "AI 助手" },
  { id: "faq", label: "常见问题" },
]

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-4 rounded-xl border border-zinc-200 bg-white p-5" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="mb-3 text-base font-semibold">
        {title}
      </h2>
      {children}
    </section>
  )
}

function Bullets({ items, ordered }: { items: string[]; ordered?: boolean }) {
  const List = ordered ? "ol" : "ul"
  return (
    <List className={`space-y-1.5 pl-5 text-zinc-700 ${ordered ? "list-decimal" : "list-disc"}`}>
      {items.map((t) => (
        <li key={t}>{t}</li>
      ))}
    </List>
  )
}

/** 报销标准表：数字来自 /api/templates（后端按 rules.yaml 计算），改标准不用改页面 */
function ExpenseStandards() {
  const q = useTemplates()
  if (q.isPending) return <Skeleton className="h-32 w-full" />
  const guides = q.data?.expense_guides ?? []
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse text-left">
        <thead className="text-zinc-500">
          <tr className="border-b border-zinc-200">
            <th className="w-24 py-2 pr-3 font-normal">类型</th>
            <th className="py-2 pr-3 font-normal">标准</th>
            <th className="py-2 pr-3 font-normal">需要填写</th>
            <th className="w-28 py-2 font-normal">票据</th>
          </tr>
        </thead>
        <tbody>
          {guides.map((g) => (
            <tr key={g.type} className="border-b border-zinc-100 align-top">
              <td className="py-2 pr-3 font-medium">{g.label}</td>
              <td className="py-2 pr-3 text-zinc-700">{g.standard}</td>
              <td className="py-2 pr-3 text-zinc-700">{g.must}</td>
              <td className="py-2 text-zinc-700">{g.attachments.join(" + ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-zinc-500">依据《费用报销管理制度》，超出标准的报销自动转主管审批。</p>
    </div>
  )
}

/** 使用说明：按当前角色的上手步骤 + 商机阶段口径 + 报销标准 + AI 能做什么 + 常见问题 */
/** 清掉「已收起」记录，回到工作台重新看到上手清单和页面提示 */
function showGuideAgain() {
  for (const key of guideKeys()) writeStorage(key, null)
  toast.success("已恢复新手引导", { description: "工作台和各页面的提示会重新出现" })
}

export default function HelpPage() {
  const { role } = useSession()
  const start = QUICK_START[role]
  return (
    <PageFrame
      title="使用说明"
      icon={BookOpen}
      bodyClassName="overflow-y-auto"
      actions={<FrameAction icon={RotateCcw} label="重新显示新手引导" onClick={showGuideAgain} />}
    >
      <div className="mx-auto w-full max-w-4xl space-y-4 p-4 sm:p-6">
        <nav aria-label="目录" className="flex flex-wrap gap-1.5">
          {SECTIONS.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="inline-flex h-7 items-center rounded-full border border-zinc-200 bg-white px-3 text-xs text-zinc-700 hover:bg-zinc-50"
            >
              {s.label}
            </a>
          ))}
        </nav>
        <Section id="start" title={start.title}>
          <Bullets items={start.steps} ordered />
        </Section>
        <Section id="stages" title="商机阶段：什么时候推进到下一步">
          <div className="space-y-2.5">
            {STAGE_GUIDE.map((s) => (
              <div key={s.stage} className="grid gap-1 sm:grid-cols-[96px_1fr_1fr] sm:gap-3">
                <div>
                  <Tag color={STAGE_META[s.stage].color}>{STAGE_META[s.stage].label}</Tag>
                </div>
                <div className="text-zinc-700">{s.meaning}</div>
                <div className="text-zinc-500">
                  <span className="text-zinc-400">下一步：</span>
                  {s.exit}
                </div>
              </div>
            ))}
          </div>
        </Section>
        <Section id="expense" title="报销怎么填">
          <Bullets items={EXPENSE_FLOW} ordered />
          <div className="mt-4">
            <ExpenseStandards />
          </div>
        </Section>
        <Section id="ai" title="AI 助手能做什么">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <div className="mb-1.5 font-medium text-emerald-700">可以</div>
              <Bullets items={AI_CAN} />
            </div>
            <div>
              <div className="mb-1.5 font-medium text-zinc-700">不会</div>
              <Bullets items={AI_CANNOT} />
            </div>
          </div>
        </Section>
        <Section id="faq" title="常见问题">
          <dl className="space-y-3">
            {FAQ.map((f) => (
              <div key={f.q}>
                <dt className="font-medium">{f.q}</dt>
                <dd className="mt-0.5 text-zinc-600">{f.a}</dd>
              </div>
            ))}
          </dl>
        </Section>
      </div>
    </PageFrame>
  )
}
