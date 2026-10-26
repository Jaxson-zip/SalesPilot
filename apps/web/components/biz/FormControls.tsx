"use client"

import { format, parseISO } from "date-fns"
import { zhCN } from "date-fns/locale"
import { CalendarDays } from "lucide-react"
import { useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"

/** 表单字段：标签 + 控件 + 提示 / 错误 */
export function FormField({
  label,
  required,
  hint,
  error,
  children,
  htmlFor,
}: {
  label: string
  required?: boolean
  hint?: ReactNode
  error?: string
  children: ReactNode
  htmlFor?: string
}) {
  return (
    <div className="min-w-0 space-y-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {label}
        {required ? <span className="ml-0.5 text-red-500">*</span> : null}
      </label>
      {children}
      {error ? (
        <p className="text-xs text-red-600">{error}</p>
      ) : hint ? (
        <p className="text-xs text-zinc-500">{hint}</p>
      ) : null}
    </div>
  )
}

/** 金额输入（元，带 ¥ 前缀）；提交时由 lib/money 转成分 */
export function MoneyInput({
  id,
  value,
  onChange,
  disabled,
  invalid,
  placeholder = "0.00",
}: {
  id?: string
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  invalid?: boolean
  placeholder?: string
}) {
  return (
    <InputGroup data-disabled={disabled}>
      <InputGroupAddon>
        <InputGroupText>¥</InputGroupText>
      </InputGroupAddon>
      <InputGroupInput
        id={id}
        inputMode="decimal"
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        aria-invalid={invalid || undefined}
        onChange={(e) => onChange(e.target.value)}
        className="tabular-nums"
      />
    </InputGroup>
  )
}

/** DatePicker（Popover + Calendar），值为 YYYY-MM-DD */
export function DatePicker({
  value,
  onChange,
  disabled,
  placeholder = "选择日期",
  size = "default",
}: {
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  placeholder?: string
  size?: "default" | "sm"
}) {
  const [open, setOpen] = useState(false)
  const date = value ? parseISO(value) : undefined
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size={size}
          disabled={disabled}
          className={cn("w-full justify-start font-normal", !value && "text-zinc-400")}
        >
          <CalendarDays className="text-zinc-500" />
          {date ? format(date, "yyyy-MM-dd") : placeholder}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          locale={zhCN}
          selected={date}
          defaultMonth={date}
          onSelect={(d) => {
            if (d) onChange(format(d, "yyyy-MM-dd"))
            setOpen(false)
          }}
        />
      </PopoverContent>
    </Popover>
  )
}

export interface Option<V extends string = string> {
  value: V
  label: string
}

/** Select（选项 ≤ 7 个） */
export function SimpleSelect<V extends string>({
  value,
  onChange,
  options,
  placeholder,
  disabled,
  size = "default",
  className,
  ariaLabel,
}: {
  value: V | ""
  onChange: (v: V) => void
  options: Option<V>[]
  placeholder?: string
  disabled?: boolean
  size?: "default" | "sm"
  className?: string
  ariaLabel?: string
}) {
  return (
    <Select
      value={value || undefined}
      onValueChange={(v) => {
        const hit = options.find((o) => o.value === v)
        if (hit) onChange(hit.value)
      }}
      disabled={disabled}
    >
      <SelectTrigger size={size} className={cn("w-full", className)} aria-label={ariaLabel}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
