"use client"

import { ChevronsUpDown, Plus } from "lucide-react"
import { useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { formatFen } from "@/lib/format"
import type { PackCatalogItem } from "@/lib/pack-rules"
import { cn } from "@/lib/utils"

export function Section({
  label,
  hint,
  add,
  children,
}: {
  label: string
  hint?: string
  add: ReactNode
  children: ReactNode
}) {
  return (
    <section aria-label={label} className="space-y-2 border-t border-zinc-200 px-3.5 py-3 first-of-type:border-t-0">
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium">{label}</span>
        {hint ? <span className="truncate text-xs text-zinc-500">{hint}</span> : null}
      </div>
      {children}
      {add}
    </section>
  )
}

export function Line({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-zinc-100 pb-2 last-of-type:border-0">
      {children}
    </div>
  )
}

/** 从产品目录选物料（可搜索，显示目录价） */
export function CatalogPicker({
  catalog,
  onPick,
}: {
  catalog: PackCatalogItem[]
  onPick: (c: PackCatalogItem) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" role="combobox" aria-expanded={open} aria-label="添加物料">
          <Plus />
          添加物料
          <ChevronsUpDown className="text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="start">
        <Command>
          <CommandInput placeholder="搜索产品目录…" />
          <CommandList>
            <CommandEmpty>没有匹配的物料</CommandEmpty>
            <CommandGroup>
              {catalog.map((c) => (
                <CommandItem
                  key={c.sku}
                  value={`${c.name} ${c.sku}`}
                  onSelect={() => {
                    onPick(c)
                    setOpen(false)
                  }}
                >
                  <span className="min-w-0 flex-1 truncate">{c.name}</span>
                  <span className="text-muted-foreground shrink-0 text-xs tabular-nums">{formatFen(c.price)}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

export const EXTRA_KINDS: { value: "service" | "passthrough"; label: string }[] = [
  { value: "service", label: "服务费" },
  { value: "passthrough", label: "代垫费用" },
]

/** 带前缀文字的小输入框（单价、成本、数量），输入后也看得出是哪一格 */
export function LabeledInput({
  label,
  prefix,
  suffix,
  placeholder,
  title,
  numeric,
  className,
  value,
  onChange,
}: {
  label: string
  prefix: string
  suffix?: string
  placeholder: string
  title?: string
  numeric?: boolean
  className?: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <InputGroup className={cn("h-8 w-36", className)} title={title}>
      <InputGroupAddon>
        <InputGroupText>{prefix}</InputGroupText>
      </InputGroupAddon>
      <InputGroupInput
        aria-label={label}
        inputMode={numeric ? "numeric" : "decimal"}
        placeholder={placeholder}
        className="tabular-nums"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {suffix ? (
        <InputGroupAddon align="inline-end">
          <InputGroupText className="max-w-12 truncate">{suffix}</InputGroupText>
        </InputGroupAddon>
      ) : null}
    </InputGroup>
  )
}

export function Row({
  label,
  value,
  strong,
  hint,
  danger,
}: {
  label: string
  value: string
  strong?: boolean
  hint?: string
  danger?: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-zinc-500">
        {label}
        {hint ? <span className="ml-1.5 text-xs text-zinc-400">{hint}</span> : null}
      </span>
      <span className={cn("tabular-nums", strong && "font-semibold", danger && "text-red-600")}>{value}</span>
    </div>
  )
}
