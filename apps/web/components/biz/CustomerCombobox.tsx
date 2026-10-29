"use client"

import { ChevronsUpDown } from "lucide-react"
import { useState } from "react"

import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { useCustomers } from "@/hooks/useCustomers"
import { useDebounced } from "@/hooks/useDebounced"
import { defaultScope } from "@/lib/views"
import { cn } from "@/lib/utils"
import type { CustomerBrief } from "@/types/api"

const LIMIT = 30

/** 关联客户 Combobox（Popover + Command）：在服务端按名称 / 行业搜索，只列出当前角色可见的客户 */
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
  const [search, setSearch] = useState("")
  const q = useDebounced(search.trim(), 250)
  const query = useCustomers({ view: defaultScope(role), q, page: 1, page_size: LIMIT }, open)
  const items = query.data?.items ?? []
  const more = (query.data?.total ?? 0) - items.length

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-invalid={invalid || undefined}
          disabled={disabled}
          className={cn("w-full justify-between font-normal", !value && "text-muted-foreground")}
        >
          <span className="truncate">{value?.name ?? placeholder}</span>
          <ChevronsUpDown className="text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput placeholder="输入客户名称…" value={search} onValueChange={setSearch} />
          <CommandList>
            <CommandEmpty>
              {query.isPending ? "加载中…" : query.isError ? "客户列表加载失败" : "没有匹配的客户"}
            </CommandEmpty>
            <CommandGroup>
              {items.map((c) => (
                <CommandItem
                  key={c.id}
                  value={`${c.name} ${c.id}`}
                  data-checked={value?.id === c.id}
                  onSelect={() => {
                    onChange(value?.id === c.id ? null : { id: c.id, name: c.name })
                    setOpen(false)
                  }}
                >
                  <span className="truncate">{c.name}</span>
                </CommandItem>
              ))}
            </CommandGroup>
            {more > 0 ? (
              <p className="text-muted-foreground px-3 py-2 text-xs">还有 {more} 个客户，输入名称缩小范围</p>
            ) : null}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
