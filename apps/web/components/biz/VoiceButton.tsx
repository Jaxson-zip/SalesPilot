"use client"

import { Mic, MicOff } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useSpeechInput } from "@/hooks/useSpeechInput"
import { cn } from "@/lib/utils"

/**
 * 话筒按钮：点一下开始说，再点一下停；识别的文字接在输入框已有内容后面。
 * 浏览器不支持语音识别时不渲染（不放点不了的按钮）。
 * pill：AI 对话框底部的圆角小按钮；ghost：表单里的文字按钮。
 */
export function VoiceButton({
  value,
  onChange,
  variant = "ghost",
  disabled,
}: {
  value: string
  onChange: (next: string) => void
  variant?: "pill" | "ghost"
  disabled?: boolean
}) {
  const { supported, listening, toggle } = useSpeechInput(value, onChange)
  if (!supported) return null
  const Icon = listening ? MicOff : Mic
  const label = listening ? "停止语音输入" : "语音输入"
  if (variant === "pill") {
    return (
      <button
        type="button"
        aria-label={label}
        aria-pressed={listening}
        title={label}
        disabled={disabled}
        onClick={toggle}
        className={cn(
          "inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full border px-3 text-xs disabled:opacity-60",
          listening ? "border-red-200 bg-red-50 text-red-700" : "border-zinc-200 text-zinc-700 hover:bg-zinc-50",
        )}
      >
        <Icon className={cn("size-3.5", listening && "animate-pulse")} />
        <span className="max-sm:hidden">{listening ? "正在听…" : "语音"}</span>
      </button>
    )
  }
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      aria-label={label}
      aria-pressed={listening}
      disabled={disabled}
      onClick={toggle}
      className={cn(listening && "text-red-700")}
    >
      <Icon className={cn(listening && "animate-pulse")} />
      {listening ? "正在听…点此停止" : "语音"}
    </Button>
  )
}
