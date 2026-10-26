"use client"

import { Check, ChevronsUpDown } from "lucide-react"
import { useState } from "react"

import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { useCustomers } from "@/hooks/useCustomers"
import { defaultScope } from "@/lib/views"
import { cn } from "@/lib/utils"
import type { CustomerBrief } from "@/types/api"

/** 关联客户 Combobox（Popover + Command，选项多、需要搜索）；只列出当前角色可见的客户 */
export function CustomerCombobox({
  value,
  onChange,
  disabled,
  invalid,
  placeholder = "搜索并选择客户",
}: {
  value: CustomerBrief | null
  onChange: (v: CustomerBrief | null) => void
  disabled?: boolean
  invalid?: boolean
  placeholder?: string
}) {
  const { role } = useSession()
  const [open, setOpen] = useState(false)
  const query = useCustomers({ view: defaultScope(role), page: 1, page_size: 100 }, open || Boolean(value))
  const items = query.data?.items ?? []

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-invalid={invalid || undefined}
          disabled={disabled}
          className={cn("w-full justify-between font-normal", !value && "text-zinc-400")}
        >
          <span className="truncate">{value?.name ?? placeholder}</span>
          <ChevronsUpDown className="text-zinc-400" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) p-0" align="start">
        <Command>
          <CommandInput placeholder="输入客户名称…" />
          <CommandList>
            <CommandEmpty>
              {query.isPending ? "加载中…" : query.isError ? "客户列表加载失败" : "没有匹配的客户"}
            </CommandEmpty>
            <CommandGroup>
              {items.map((c) => (
                <CommandItem
                  key={c.id}
                  value={`${c.name} ${c.id}`}
                  onSelect={() => {
                    onChange(value?.id === c.id ? null : { id: c.id, name: c.name })
                    setOpen(false)
                  }}
                >
                  <span className="truncate">{c.name}</span>
                  <Check className={cn("ml-auto", value?.id === c.id ? "opacity-100" : "opacity-0")} />
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
