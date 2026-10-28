"use client"

import { ArrowUp, Boxes, Cpu, Lock } from "lucide-react"
import { useRef, type KeyboardEvent } from "react"

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useAgentModels } from "@/hooks/useAgentModels"
import { modelOptions, ruleModeHint } from "@/lib/agent-models"
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

/**
 * 模型选择：pill 变体 Select（只用于 AI 输入框底部）。
 * 选项来自网关能力表；没配 Key 的模型标「未配置」不可选；全部不可用时显示「规则模式」。
 */
function ModelSelect({ model, onModelChange }: { model: string; onModelChange: (model: string) => void }) {
  const { data } = useAgentModels()
  const hint = ruleModeHint(data)
  const options = modelOptions(data)
  const current = options.find((m) => m.value === model)
  const groups = [
    { label: "自动切换", items: options.filter((m) => m.kind === "auto") },
    { label: "指定模型", items: options.filter((m) => m.kind === "model") },
  ].filter((g) => g.items.length > 0)
  return (
    <>
      <Select value={model} onValueChange={onModelChange}>
        <SelectTrigger
          size="sm"
          aria-label="选择模型"
          title="选择回答用的大模型"
          className="h-8 shrink-0 gap-1.5 rounded-full border-zinc-200 px-3 text-xs text-zinc-700 shadow-none hover:bg-zinc-50"
        >
          <Cpu className="size-3.5 text-zinc-500" />
          <span className="text-zinc-400 max-sm:hidden">模型</span>
          <SelectValue>
            {current ? (
              <>
                {current.label}
                {current.detail ? <span className="text-zinc-400 max-sm:hidden"> · {current.detail}</span> : null}
              </>
            ) : (
              model
            )}
          </SelectValue>
        </SelectTrigger>
        <SelectContent className="min-w-56">
          {groups.map((g, i) => (
            <SelectGroup key={g.label}>
              {i > 0 ? <SelectSeparator /> : null}
              <SelectLabel>{g.label}</SelectLabel>
              {g.items.map((m) => (
                <SelectItem key={m.value} value={m.value} disabled={!m.available}>
                  {m.label}
                  {m.detail ? <span className="text-zinc-400">（{m.detail}，失败时换下一个）</span> : null}
                  {m.available ? null : <span className="text-zinc-400">（未配置 Key）</span>}
                </SelectItem>
              ))}
            </SelectGroup>
          ))}
        </SelectContent>
      </Select>
      {hint ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-flex h-8 shrink-0 cursor-help items-center rounded-full bg-amber-50 px-3 text-xs text-amber-800">
              规则模式
            </span>
          </TooltipTrigger>
          <TooltipContent>{hint}</TooltipContent>
        </Tooltip>
      ) : null}
    </>
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
      aria-label={streaming ? "停止生成" : "发送"}
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
        <SendButton streaming={streaming} disabled={!streaming && !canSend} onClick={streaming ? onStop : onSubmit} />
      </div>
    </div>
  )
}
