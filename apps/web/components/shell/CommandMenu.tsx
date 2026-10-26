"use client"

import { Plus, Receipt, Sparkles } from "lucide-react"
import { useRouter } from "next/navigation"
import { useEffect } from "react"

import { useSession } from "@/components/shell/SessionProvider"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import { navItemsFor } from "@/lib/nav"
import { canCreateBusiness } from "@/lib/permissions"

/** Ctrl K 全局命令面板（CommandDialog） */
export function CommandMenu({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const router = useRouter()
  const { role } = useSession()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        onOpenChange(!open)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onOpenChange])

  const go = (href: string) => {
    onOpenChange(false)
    router.push(href)
  }

  const pages = navItemsFor(role)
  const canWrite = canCreateBusiness(role)

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="全局搜索"
      description="搜索客户、商机、报价单，或输入命令"
    >
      <CommandInput placeholder="搜索客户、商机、报价单，或输入命令…" />
      <CommandList>
        <CommandEmpty>没有匹配的结果</CommandEmpty>
        {canWrite ? (
          <>
            <CommandGroup heading="快捷操作">
              <CommandItem onSelect={() => go("/ai")}>
                <Sparkles className="text-ai" />
                AI 出方案报价
              </CommandItem>
              <CommandItem onSelect={() => go("/customers")}>
                <Plus />
                新建客户
              </CommandItem>
              <CommandItem onSelect={() => go("/expenses")}>
                <Receipt />
                新建报销
              </CommandItem>
            </CommandGroup>
            <CommandSeparator />
          </>
        ) : null}
        <CommandGroup heading="页面">
          {pages.map((p) => (
            <CommandItem key={p.href} value={`${p.label} ${p.href}`} onSelect={() => go(p.href)}>
              <p.icon />
              {p.label}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
