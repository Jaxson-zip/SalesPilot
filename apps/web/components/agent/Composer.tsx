"use client"

import { ArrowUp, Cpu, FileText, Images, Loader2, Paperclip, RotateCw, X } from "lucide-react"
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
import { PackChip, PackSelect } from "@/components/agent/PackChip"
import { VoiceButton } from "@/components/biz/VoiceButton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useAgentModels } from "@/hooks/useAgentModels"
import { modelOptions, ruleModeHint } from "@/lib/agent-models"
import { MATERIAL_ACCEPT, MATERIAL_DEFAULT_ASK, type MaterialOut } from "@/lib/materials"
import {
  MAX_SAMPLES,
  SAMPLE_ACCEPT,
  SAMPLE_DEFAULT_ASK,
  samplesBusy,
  samplesLabel,
  toSamplesIn,
  type SampleState,
} from "@/lib/samples"
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
  /** 没关联商机时可以选行业包：传了就显示下拉，代替只读标签 */
  packPicker?: { value: string; onChange: (pack: string) => void } | null
  compact?: boolean
  rows?: number
  placeholder?: string
  /** 一手材料：传了 onAttach 才显示「上传材料」按钮 */
  material?: MaterialOut | null
  uploading?: boolean
  onAttach?: (file: File) => void
  onClearMaterial?: () => void
  /** 客户样例图片：传了 onAttachSamples 才显示「样例图片」按钮 */
  samples?: SampleState | null
  onAttachSamples?: (files: File[]) => void
  onRetrySamples?: () => void
  onClearSamples?: () => void
}

const KIND_LABEL: Record<MaterialOut["kind"], string> = {
  text: "文本",
  docx: "Word",
  pdf: "PDF",
  image: "图片识别",
}

/** 已上传的材料：名称、字数，可移除 */
function MaterialChip({ material, onClear }: { material: MaterialOut; onClear?: () => void }) {
  return (
    <div className="mx-3 mt-3 flex items-center gap-2 rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs">
      <FileText className="size-4 shrink-0 text-zinc-500" />
      <span className="min-w-0 truncate font-medium text-zinc-800">{material.name}</span>
      <span className="shrink-0 text-zinc-400">
        {KIND_LABEL[material.kind]} · {material.chars.toLocaleString()} 字
        {material.truncated ? "（只取前 12000 字）" : ""}
      </span>
      <div className="flex-1" />
      <button
        type="button"
        aria-label="移除材料"
        onClick={onClear}
        className="rounded p-0.5 text-zinc-400 hover:bg-zinc-200 hover:text-zinc-700"
      >
        <X className="size-3.5" />
      </button>
    </div>
  )
}

/** 样例图片标签：识别进度 → 张数和单据类数；有失败的可以重试 */
function SamplesChip({
  samples,
  onRetry,
  onClear,
}: {
  samples: SampleState
  onRetry?: () => void
  onClear?: () => void
}) {
  const busy = samplesBusy(samples)
  return (
    <div
      aria-label="客户样例图片"
      className="mx-3 mt-3 flex items-center gap-2 rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs"
    >
      {busy ? (
        <Loader2 className="size-4 shrink-0 animate-spin text-zinc-500" />
      ) : (
        <Images className="size-4 shrink-0 text-zinc-500" />
      )}
      <span className="min-w-0 truncate font-medium text-zinc-800">客户样例图片</span>
      <span className="shrink-0 text-zinc-400">{samplesLabel(samples)}</span>
      <div className="flex-1" />
      {!busy && samples.failed.length > 0 ? (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-zinc-600 hover:bg-zinc-200"
        >
          <RotateCw className="size-3" />
          重试失败的
        </button>
      ) : null}
      <button
        type="button"
        aria-label="移除样例图片"
        onClick={onClear}
        className="rounded p-0.5 text-zinc-400 hover:bg-zinc-200 hover:text-zinc-700"
      >
        <X className="size-3.5" />
      </button>
    </div>
  )
}

/** 样例图片按钮：客户发来的单据 / 表单样例（可多选），AI 识别类型和字段后出方案 */
function SamplesButton({ busy, onPick }: { busy?: boolean; onPick: (files: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="上传样例图片"
          disabled={busy}
          onClick={() => input.current?.click()}
          className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full border border-zinc-200 px-3 text-xs text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
        >
          <Images className="size-3.5" />
          <span className="max-sm:hidden">样例图片</span>
          <input
            ref={input}
            type="file"
            hidden
            multiple
            accept={SAMPLE_ACCEPT}
            data-testid="samples-input"
            onChange={(e) => {
              const files = Array.from(e.target.files ?? [])
              e.target.value = ""
              if (files.length) onPick(files)
            }}
          />
        </button>
      </TooltipTrigger>
      <TooltipContent>
        上传客户发来的单据 / 表单样例图片（最多 {MAX_SAMPLES} 张），AI 识别单据类型、字段和清晰度后出方案
      </TooltipContent>
    </Tooltip>
  )
}

/** 上传材料按钮：会议纪要、聊天记录、名片截图 → AI 整理成跟进 / 联系人 / 下一步 */
function AttachButton({ uploading, onPick }: { uploading?: boolean; onPick: (file: File) => void }) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="上传材料"
          disabled={uploading}
          onClick={() => input.current?.click()}
          className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full border border-zinc-200 px-3 text-xs text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
        >
          {uploading ? <Loader2 className="size-3.5 animate-spin" /> : <Paperclip className="size-3.5" />}
          <span className="max-sm:hidden">{uploading ? "读取中…" : "上传材料"}</span>
          <input
            ref={input}
            type="file"
            hidden
            accept={MATERIAL_ACCEPT}
            data-testid="material-input"
            onChange={(e) => {
              const file = e.target.files?.[0]
              e.target.value = ""
              if (file) onPick(file)
            }}
          />
        </button>
      </TooltipTrigger>
      <TooltipContent>
        上传会议纪要、聊天记录、名片截图（Word / PDF / 文本 / 图片），AI 整理成跟进、联系人和下一步
      </TooltipContent>
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
    packPicker,
    compact,
    rows = 2,
    placeholder,
    material,
    uploading,
    onAttach,
    onClearMaterial,
    samples,
    onAttachSamples,
    onRetrySamples,
    onClearSamples,
  } = props
  const composing = useRef(false)
  const busy = samplesBusy(samples ?? null)
  const canSend =
    (value.trim().length > 0 || Boolean(material) || Boolean(toSamplesIn(samples ?? null))) && !uploading && !busy

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !composing.current) {
      e.preventDefault()
      if (!streaming && canSend) onSubmit()
    }
  }

  return (
    <div className="rounded-[20px] border border-zinc-200 bg-white shadow-sm focus-within:border-zinc-300">
      {material ? <MaterialChip material={material} onClear={onClearMaterial} /> : null}
      {samples ? <SamplesChip samples={samples} onRetry={onRetrySamples} onClear={onClearSamples} /> : null}
      <textarea
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onCompositionStart={() => (composing.current = true)}
        onCompositionEnd={() => (composing.current = false)}
        placeholder={
          material
            ? `可以补充说明，例如：这是和明理律所的拜访纪要（不填则「${MATERIAL_DEFAULT_ASK}」）`
            : samples
              ? `可以补充说明，例如：报关单据，每天约 200 票，审核后导出（不填则「${SAMPLE_DEFAULT_ASK}」）`
              : (placeholder ?? "给 SalesPilot 发消息，例如：给明理律所出一份 Qwen3-32B 私有化方案")
        }
        className="w-full resize-none bg-transparent px-4 pt-3.5 text-base outline-none placeholder:text-zinc-400 md:text-[14px]"
      />
      <div className="flex min-w-0 items-center gap-1.5 px-3 pb-3">
        {compact ? null : packPicker ? (
          <PackSelect value={packPicker.value} onChange={packPicker.onChange} />
        ) : pack ? (
          <PackChip pack={pack} />
        ) : null}
        {onAttach ? <AttachButton uploading={uploading} onPick={onAttach} /> : null}
        {onAttachSamples ? <SamplesButton busy={busy} onPick={onAttachSamples} /> : null}
        <VoiceButton value={value} onChange={onChange} variant="pill" disabled={streaming} />
        <ModelSelect model={model} onModelChange={onModelChange} />
        <div className="flex-1" />
        <SendButton streaming={streaming} disabled={!streaming && !canSend} onClick={streaming ? onStop : onSubmit} />
      </div>
    </div>
  )
}
