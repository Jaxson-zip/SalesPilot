"use client"

import { Sparkles } from "lucide-react"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { toast } from "sonner"

import { VoiceButton } from "@/components/biz/VoiceButton"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { digestPrompt, MATERIAL_MAX_CHARS, pastedMaterial, stashPastedMaterial } from "@/lib/materials"
import { aiPrefillHref } from "@/lib/thread-history"

/**
 * 粘贴沟通纪要 / 微信聊天记录 / 录音转写 → 交给 AI 工作台提炼：
 * 跟进记录（重点、客户关注点）+ 新联系人 + 下一步任务，写入前在对话里确认。
 */
export function PasteNotesDialog({
  open,
  onOpenChange,
  customer,
  opportunity,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  customer: string
  opportunity?: { id: string; name: string }
}) {
  const router = useRouter()
  const [text, setText] = useState("")
  const long = text.trim().length > MATERIAL_MAX_CHARS
  const go = () => {
    if (!stashPastedMaterial(pastedMaterial(text, customer))) {
      toast.error("浏览器禁止了本地存储，请把纪要另存为 .txt 后在 AI 工作台上传")
      return
    }
    const href = aiPrefillHref(digestPrompt(customer, opportunity?.name), opportunity?.id)
    setText("")
    onOpenChange(false)
    router.push(`${href}&paste=1`)
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>粘贴纪要，AI 提炼跟进</DialogTitle>
          <DialogDescription>
            把会议纪要、微信聊天记录或录音转写的文字粘贴进来，AI 会提炼跟进重点和客户关注点、补充联系人、安排下一步，
            写入前会先给你确认。
          </DialogDescription>
        </DialogHeader>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          autoFocus
          aria-label="沟通纪要"
          placeholder={"例如：\n王总：下季度预算已经批了，最关心数据能不能留在本地…\n我：下周三之前给您发两套部署方案…"}
          className="block w-full resize-y rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400"
        />
        <div className="flex items-center justify-between gap-2 text-xs text-zinc-500">
          <VoiceButton value={text} onChange={setText} />
          <span className="min-w-0 flex-1">
            {long ? `超过 ${MATERIAL_MAX_CHARS.toLocaleString()} 字，只交给 AI 前面这部分` : "粘贴后可以先删掉无关内容"}
          </span>
          <span className="tabular-nums">{text.trim().length.toLocaleString()} 字</span>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={!text.trim()} onClick={go}>
            <Sparkles />
            交给 AI 提炼
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
