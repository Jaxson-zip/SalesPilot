"use client"

import type { LucideIcon } from "lucide-react"
import { useEffect, useRef, useState, type ReactNode } from "react"

import { DatePicker, SimpleSelect } from "@/components/biz/FormControls"
import { Input } from "@/components/ui/input"
import { parseInline, toInlineText, type InlineSpec } from "@/lib/inline-edit"
import { cn } from "@/lib/utils"

export interface InlineEditProps extends InlineSpec {
  icon: LucideIcon
  label: string
  /** 只读显示 */
  display: ReactNode
  /** 接口原值（金额为分） */
  value: string | number | null
  editable: boolean
  /** 保存成功后 resolve；失败时 reject（错误由 mutation 的 onError 提示），保持编辑状态 */
  onSave: (value: string | number | null) => Promise<unknown>
  options?: { value: string; label: string }[]
  placeholder?: string
}

/** 当前值不在预设选项里（历史数据）时补进去，否则下拉显示为空 */
function withCurrent(options: { value: string; label: string }[], current: string) {
  return !current || options.some((o) => o.value === current)
    ? options
    : [{ value: current, label: current }, ...options]
}

/**
 * 记录详情的字段行（U10 行内编辑，Twenty 的做法）：点值进入编辑；
 * 文本 / 金额 / 整数回车或失焦保存、Esc 取消；日期和下拉选中即保存。值没变不发请求。
 */
export function InlineEditRow({
  icon: Icon,
  label,
  display,
  value,
  editable,
  onSave,
  options,
  placeholder,
  ...spec
}: InlineEditProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")
  const [error, setError] = useState<string>()
  const [saving, setSaving] = useState(false)

  const start = () => {
    setDraft(toInlineText(value, spec.kind))
    setError(undefined)
    setEditing(true)
  }
  // Esc 只退出编辑、不关闭外层侧栏：Radix Dialog 在 document 捕获阶段监听 Esc，
  // 所以编辑时在更早的 window 捕获阶段拦下
  useEffect(() => {
    if (!editing) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return
      e.stopPropagation()
      setEditing(false)
    }
    window.addEventListener("keydown", onKey, true)
    return () => window.removeEventListener("keydown", onKey, true)
  }, [editing])

  // 回车保存后输入框被禁用会再触发一次失焦：用 ref 挡掉重复提交（state 在闭包里还是旧值）
  const inFlight = useRef(false)

  const commit = async (raw: string) => {
    if (inFlight.current) return
    const parsed = parseInline(raw, spec)
    if (!parsed.ok) return setError(parsed.error)
    if (parsed.value === value || (parsed.value === null && (value === null || value === ""))) {
      return setEditing(false)
    }
    inFlight.current = true
    setSaving(true)
    try {
      await onSave(parsed.value)
      setEditing(false)
    } catch {
      // 保持编辑状态，提示由 mutation 负责
    } finally {
      inFlight.current = false
      setSaving(false)
    }
  }

  let control: ReactNode
  if (!editing) {
    control = editable ? (
      <button
        type="button"
        aria-label={`编辑${label}`}
        onClick={start}
        className="block w-full min-w-0 truncate rounded px-1.5 py-1 text-left hover:bg-zinc-100"
      >
        {display}
      </button>
    ) : (
      <div className="min-w-0 truncate px-1.5 py-1">{display}</div>
    )
  } else if (spec.kind === "date") {
    control = (
      <DatePicker value={draft} onChange={(v) => void commit(v)} ariaLabel={label} size="sm" disabled={saving} />
    )
  } else if (spec.kind === "select") {
    control = (
      <SimpleSelect
        value={draft}
        onChange={(v) => void commit(v)}
        options={withCurrent(options ?? [], draft)}
        ariaLabel={label}
        size="sm"
        disabled={saving}
      />
    )
  } else {
    control = (
      <Input
        autoFocus
        aria-label={label}
        aria-invalid={Boolean(error) || undefined}
        value={draft}
        placeholder={placeholder}
        disabled={saving}
        inputMode={spec.kind === "text" ? undefined : "decimal"}
        className="h-8"
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => void commit(draft)}
        onKeyDown={(e) => {
          if (e.key === "Enter") void commit(draft)
        }}
      />
    )
  }

  return (
    <div className="flex min-h-8 items-start">
      <span className="inline-flex h-8 w-[104px] shrink-0 items-center gap-1.5 text-zinc-500">
        <Icon className="size-3.5" />
        {label}
      </span>
      <div className={cn("min-w-0 flex-1", editing && "py-0.5")}>
        {control}
        {editing && error ? <p className="mt-1 text-xs text-red-600">{error}</p> : null}
      </div>
    </div>
  )
}
