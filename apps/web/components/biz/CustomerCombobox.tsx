"use client"

import { ChevronsUpDown, Plus } from "lucide-react"
import { useState } from "react"

import { NewCustomerSheet } from "@/components/customers/NewCustomerSheet"
import { useSession } from "@/components/shell/SessionProvider"
import { Button } from "@/components/ui/button"
import { Command, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { useCustomers } from "@/hooks/useCustomers"
import { useDebounced } from "@/hooks/useDebounced"
import { usePermissions } from "@/hooks/usePermissions"
import { comboLabel } from "@/lib/a11y"
import { createCustomerLabel } from "@/lib/customer"
import { defaultScope } from "@/lib/views"
import { cn } from "@/lib/utils"
import type { CustomerBrief } from "@/types/api"

const LIMIT = 30

/**
 * 关联客户 Combobox（Popover + Command）：在服务端按名称 / 行业搜索，只列出当前角色可见的客户。
 * 能新建客户的角色在列表底部有「新建客户」：用输入的名称预填，建好后自动选中、留在原表单
 * （回归：新建商机时客户还没建，只能关掉表单去客户页，填过的内容全丢）。
 */
export function CustomerCombobox({
  value,
  onChange,
  disabled,
  invalid,
  placeholder = "搜索并选择客户",
  ariaLabel = "客户",
}: {
  value: CustomerBrief | null
  onChange: (v: CustomerBrief | null) => void
  disabled?: boolean
  invalid?: boolean
  placeholder?: string
  /** 读屏名称：combobox 不会用按钮文字当名称（回归：无障碍扫描报「客户选择控件没有名称」，critical） */
  ariaLabel?: string
}) {
  const { role } = useSession()
  const { canCreate } = usePermissions()
  const [open, setOpen] = useState(false)
  /** 正在新建的客户名称；null 表示没有在新建 */
  const [creating, setCreating] = useState<string | null>(null)
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
          aria-label={comboLabel(ariaLabel, value?.name ?? placeholder)}
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
            {/* 底部常驻「新建客户」，CommandEmpty 不会出现，没有结果时自己显示说明 */}
            {items.length === 0 ? (
              <p className="text-muted-foreground py-6 text-center text-sm">
                {query.isPending ? "加载中…" : query.isError ? "客户列表加载失败" : "没有匹配的客户"}
              </p>
            ) : null}
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
            {canCreate ? (
              <CommandGroup className="border-t border-zinc-100">
                <CommandItem
                  value="__create__"
                  onSelect={() => {
                    setOpen(false)
                    setCreating(search.trim())
                  }}
                >
                  <Plus />
                  <span className="truncate">{createCustomerLabel(search)}</span>
                </CommandItem>
              </CommandGroup>
            ) : null}
          </CommandList>
        </Command>
      </PopoverContent>
      {creating !== null ? (
        <NewCustomerSheet
          open
          initialName={creating}
          onOpenChange={(o) => !o && setCreating(null)}
          onCreated={(c) => {
            setCreating(null)
            onChange(c)
          }}
        />
      ) : null}
    </Popover>
  )
}
