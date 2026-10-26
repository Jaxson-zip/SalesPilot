import { Sparkles } from "lucide-react"
import type { ReactNode } from "react"

import { PromptCards, QUERY_PROMPTS } from "@/components/agent/PromptCards"

/** 新对话欢迎页：标题 + 输入框 + 4 张快捷提示卡片 */
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
  return (
    <div className="flex min-w-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-6 sm:px-6">
      <div className="w-full max-w-[720px]">
        <div className="mb-2 flex items-center justify-center gap-3 text-center">
          <span className="text-ai inline-flex size-10 shrink-0 items-center justify-center rounded-full border border-zinc-200">
            <Sparkles className="size-5" />
          </span>
          <span className="text-lg font-semibold sm:text-[22px]">
            {readOnly ? "想了解哪些业务数据？" : "今天要给哪位客户出方案？"}
          </span>
        </div>
        <p className="mb-6 text-center text-zinc-500">
          {readOnly
            ? "我可以帮你查询客户、商机、报价、合同和提成（管理员只读，不能出方案或修改业务数据）"
            : "我可以帮你出方案报价、记跟进、推进商机、算提成和报销"}
        </p>
        {composer}
        {readOnly ? <PromptCards prompts={QUERY_PROMPTS} onPick={onPick} /> : <PromptCards onPick={onPick} />}
      </div>
    </div>
  )
}
