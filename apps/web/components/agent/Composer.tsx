"use client"

import { ArrowUp, Boxes, Cpu, Lock, Paperclip } from "lucide-react"
import { useRef, type KeyboardEvent } from "react"

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { MODEL_OPTIONS } from "@/lib/agent-labels"
import { cn } from "@/lib/utils"

interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  onStop?: () => void
  streaming?: boolean
  model: string
  onModelChange: (model: string) => void
  /** 行业包只读标签（来自商机产品线）；null 不显示 */
  pack?: string | null
  compact?: boolean
  rows?: number
  placeholder?: string
}

/** 行业包只读标签：锁图标，销售不能切换 */
function PackChip({ pack }: { pack: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex h-8 min-w-0 cursor-help items-center gap-1.5 rounded-full bg-zinc-100 px-3 text-xs text-zinc-600">
          <Boxes className="size-3.5 shrink-0" />
          <span className="truncate">
            {pack}
            <span className="max-sm:hidden"> · 按商机产品线自动匹配</span>
          </span>
          <Lock className="size-3 shrink-0 text-zinc-400" />
        </span>
      </TooltipTrigger>
      <TooltipContent>行业包由管理员配置，根据商机的产品线自动匹配，销售无需也不能切换</TooltipContent>
    </Tooltip>
  )
}

/** 模型选择：pill 变体 Select（只用于 AI 输入框底部） */
function ModelSelect({ model, onModelChange }: { model: string; onModelChange: (model: string) => void }) {
  return (
    <Select value={model} onValueChange={onModelChange}>
      <SelectTrigger
        size="sm"
        className="h-8 shrink-0 gap-1.5 rounded-full border-zinc-200 px-3 text-xs text-zinc-700 shadow-none hover:bg-zinc-50"
      >
        <Cpu className="size-3.5 text-zinc-500" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {MODEL_OPTIONS.map((m) => (
          <SelectItem key={m.value} value={m.value}>
            {m.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/** 发送 / 停止按钮：流式输出时变成「停止」 */
function SendButton({
  streaming,
  disabled,
  onClick,
}: {
  streaming?: boolean
  disabled: boolean
  onClick?: () => void
}) {
  return (
    <button
      type="button"
      title={streaming ? "停止生成" : "发送"}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "bg-primary text-primary-foreground inline-flex size-8 shrink-0 items-center justify-center rounded-full hover:bg-zinc-700",
        "disabled:cursor-not-allowed disabled:opacity-40",
      )}
    >
      {streaming ? <span className="size-2.5 rounded-[2px] bg-white" /> : <ArrowUp className="size-4" />}
    </button>
  )
}

/** Composer：DeepSeek 风格大圆角输入框（20px），Enter 发送、Shift+Enter 换行 */
export function Composer(props: ComposerProps) {
  const {
    value,
    onChange,
    onSubmit,
    onStop,
    streaming,
    model,
    onModelChange,
    pack,
    compact,
    rows = 2,
    placeholder,
  } = props
  const composing = useRef(false)
  const canSend = value.trim().length > 0

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !composing.current) {
      e.preventDefault()
      if (!streaming && canSend) onSubmit()
    }
  }

  return (
    <div className="rounded-[20px] border border-zinc-200 bg-white shadow-sm focus-within:border-zinc-300">
      <textarea
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onCompositionStart={() => (composing.current = true)}
        onCompositionEnd={() => (composing.current = false)}
        placeholder={placeholder ?? "给 SalesPilot 发消息，例如：给明理律所出一份 Qwen3-32B 私有化方案"}
        className="w-full resize-none bg-transparent px-4 pt-3.5 text-[14px] outline-none placeholder:text-zinc-400"
      />
      <div className="flex min-w-0 items-center gap-1.5 px-3 pb-3">
        {!compact && pack ? <PackChip pack={pack} /> : null}
        <ModelSelect model={model} onModelChange={onModelChange} />
        <div className="flex-1" />
        <button
          type="button"
          title="上传附件"
          className="inline-flex size-8 shrink-0 items-center justify-center rounded-full text-zinc-500 hover:bg-zinc-100"
        >
          <Paperclip className="size-4" />
        </button>
        <SendButton streaming={streaming} disabled={!streaming && !canSend} onClick={streaming ? onStop : onSubmit} />
      </div>
    </div>
  )
}
