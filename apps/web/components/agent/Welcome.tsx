"use client"

import { Paperclip, Sparkles } from "lucide-react"
import type { ReactNode } from "react"

import { PromptCards } from "@/components/agent/PromptCards"
import { useSession } from "@/components/shell/SessionProvider"
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

/** 新对话欢迎页：标题 + 输入框 + 按角色的示例问题卡片 */
export function Welcome({
  composer,
  onPick,
  readOnly,
}: {
  composer: ReactNode
  onPick: (prompt: string) => void
  /** 管理员：只能对话查询，不出方案、不做写操作 */
  readOnly?: boolean
}) {
  const { role } = useSession()
  const intro = INTRO[readOnly ? "admin" : role]
  return (
    // my-auto 居中：justify-center + overflow 时内容超高，顶部会被裁掉且滚不上去
    <div className="flex min-w-0 flex-1 flex-col items-center overflow-y-auto px-4 py-6 sm:px-6">
      <div className="my-auto w-full max-w-[720px]">
        <div className="mb-2 flex items-center justify-center gap-3 text-center">
          <span className="text-ai inline-flex size-10 shrink-0 items-center justify-center rounded-full border border-zinc-200">
            <Sparkles className="size-5" />
          </span>
          <span className="text-lg font-semibold sm:text-[22px]">{intro.title}</span>
        </div>
        <p className="mb-6 text-center text-zinc-500">{intro.desc}</p>
        {composer}
        <PromptCards onPick={onPick} />
        {readOnly ? null : (
          <p className="mt-4 flex items-center justify-center gap-1.5 text-center text-xs text-zinc-500">
            <Paperclip className="size-3.5 shrink-0" />
            有会议纪要、聊天记录或名片？点输入框里的「上传材料」，AI 会整理成跟进、联系人和下一步
          </p>
        )}
      </div>
    </div>
  )
}
