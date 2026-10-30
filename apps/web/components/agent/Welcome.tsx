"use client"

import { GraduationCap, Info, Sparkles } from "lucide-react"
import type { ReactNode } from "react"

import { ModeSwitch } from "@/components/agent/ModeSwitch"
import { PromptCards } from "@/components/agent/PromptCards"
import { useSession } from "@/components/shell/SessionProvider"
import { usePacks } from "@/hooks/useProductLines"
import type { AgentMode } from "@/lib/agent-mode"
import type { Role } from "@/types/api"

/** 每个角色的欢迎语：只说 AI 真正能做的事（与 chat_tools_for 的工具范围一致） */
const INTRO: Record<Role, { title: string; desc: string }> = {
  sales: {
    title: "今天要给哪位客户出方案？",
    desc: "出方案报价、记跟进、推进商机、报销，直接说就行",
  },
  manager: {
    title: "今天先看看团队情况？",
    desc: "看团队漏斗、处理审批、查制度，直接说就行",
  },
  admin: {
    title: "想了解哪些业务数据？",
    desc: "查客户、商机和全公司漏斗（只读）",
  },
}

const LEARN_INTRO = {
  title: "刚入职？先了解公司业务",
  desc: "按公司知识库和业务规则回答，标出处，查不到会直说",
}

/** 行业包还是示例资料时提醒：学习问答的回答基于示例内容 */
function SampleNotice() {
  const { data } = usePacks()
  if (!data?.some((p) => p.sample_data)) return null
  return (
    <p className="mt-4 flex items-start justify-center gap-1.5 text-center text-xs text-amber-700">
      <Info className="mt-px size-3.5 shrink-0" />
      现在是示例资料，适合熟悉业务和系统
    </p>
  )
}

/** 新对话欢迎页：模式切换 + 标题 + 输入框 + 示例问题卡片 */
export function Welcome({
  composer,
  onPick,
  readOnly,
  mode = "work",
  onModeChange,
}: {
  composer: ReactNode
  onPick: (prompt: string) => void
  /** 管理员：只能对话查询，不出方案、不做写操作 */
  readOnly?: boolean
  mode?: AgentMode
  onModeChange?: (mode: AgentMode) => void
}) {
  const { role } = useSession()
  const learn = mode === "learn"
  const intro = learn ? LEARN_INTRO : INTRO[readOnly ? "admin" : role]
  const Icon = learn ? GraduationCap : Sparkles
  return (
    // my-auto 居中：justify-center + overflow 时内容超高，顶部会被裁掉且滚不上去
    <div className="flex min-w-0 flex-1 flex-col items-center overflow-y-auto px-4 py-6 sm:px-6">
      <div className="my-auto w-full max-w-[720px]">
        {onModeChange ? (
          <div className="mb-5 flex justify-center">
            <ModeSwitch mode={mode} onChange={onModeChange} />
          </div>
        ) : null}
        <div className="mb-2 flex items-center justify-center gap-3 text-center">
          <span className="text-ai inline-flex size-10 shrink-0 items-center justify-center rounded-full border border-zinc-200">
            <Icon className="size-5" />
          </span>
          <span className="text-lg font-semibold sm:text-[22px]">{intro.title}</span>
        </div>
        <p className="mb-6 text-center text-zinc-500">{intro.desc}</p>
        {composer}
        <PromptCards onPick={onPick} learn={learn} />
        {learn ? <SampleNotice /> : null}
      </div>
    </div>
  )
}
