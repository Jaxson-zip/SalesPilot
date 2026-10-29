"use client"

import { GraduationCap, Images, Info, Paperclip, Sparkles } from "lucide-react"
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
    desc: "我可以帮你出方案报价、记跟进、推进商机、安排下一步、对话报销，也可以查公司制度",
  },
  manager: {
    title: "今天先看看团队情况？",
    desc: "我可以帮你看团队商机漏斗、列出待审批的报价和报销并协助处理，也可以查公司制度",
  },
  admin: {
    title: "想了解哪些业务数据？",
    desc: "我可以帮你查客户和商机、看全公司商机漏斗、查公司制度（管理员只读，不能修改业务数据）",
  },
}

const LEARN_INTRO = {
  title: "刚入职？先了解公司业务",
  desc: "按公司知识库、业务规则和竞品战卡回答，每条都标出处；查不到会直接说没找到，不会编",
}

/** 行业包还是示例资料时提醒：学习问答的回答基于示例内容 */
function SampleNotice() {
  const { data } = usePacks()
  if (!data?.some((p) => p.sample_data)) return null
  return (
    <p className="mt-4 flex items-start justify-center gap-1.5 text-center text-xs text-amber-700">
      <Info className="mt-px size-3.5 shrink-0" />
      当前产品目录和知识库是系统内置的示例资料，适合熟悉业务和系统；管理员可在「行业包配置」换成公司真实资料
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
        {readOnly || learn ? null : (
          <p className="mt-4 flex items-center justify-center gap-1.5 text-center text-xs text-zinc-500">
            <Paperclip className="size-3.5 shrink-0" />
            有会议纪要、聊天记录或名片？点输入框里的「上传材料」，AI 会整理成跟进、联系人和下一步
          </p>
        )}
        {readOnly || learn ? null : (
          <p className="mt-1.5 flex items-center justify-center gap-1.5 text-center text-xs text-zinc-500">
            <Images className="size-3.5 shrink-0" />
            客户发来单据或表单样例？点「样例图片」，AI 识别单据类型和字段后出方案
          </p>
        )}
      </div>
    </div>
  )
}
