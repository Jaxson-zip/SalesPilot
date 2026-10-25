import { Sparkles } from "lucide-react"
import type { ReactNode } from "react"

import { PromptCards } from "@/components/agent/PromptCards"

/** 新对话欢迎页：标题 + 输入框 + 4 张快捷提示卡片 */
export function Welcome({ composer, onPick }: { composer: ReactNode; onPick: (prompt: string) => void }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-6 sm:px-6">
      <div className="w-full max-w-[720px]">
        <div className="mb-2 flex items-center justify-center gap-3 text-center">
          <span className="text-ai inline-flex size-10 shrink-0 items-center justify-center rounded-full border border-zinc-200">
            <Sparkles className="size-5" />
          </span>
          <span className="text-lg font-semibold sm:text-[22px]">今天要给哪位客户出方案？</span>
        </div>
        <p className="mb-6 text-center text-zinc-500">我可以帮你出方案报价、记跟进、推进商机、算提成和报销</p>
        {composer}
        <PromptCards onPick={onPick} />
      </div>
    </div>
  )
}
