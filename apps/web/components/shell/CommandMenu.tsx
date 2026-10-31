"use client"

import { useQuery } from "@tanstack/react-query"
import { Building2, FileText, Loader2, Plus, Receipt, Sparkles, Target } from "lucide-react"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { useSession } from "@/components/shell/SessionProvider"
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import { useDebounced } from "@/hooks/useDebounced"
import { api } from "@/lib/api"
import { formatFen } from "@/lib/format"
import { navItemsFor } from "@/lib/nav"
import { canCreateBusiness } from "@/lib/permissions"

interface Hit {
  id: string
  title: string
  sub: string
  href: string
}

interface SearchResult {
  customers: Hit[]
  opportunities: Hit[]
  quotes: Hit[]
}

type Brief = { name: string } | null | undefined
const LIMIT = 5

/** 按关键词查客户、商机、报价单（数据范围由 core 按角色决定：销售本人、主管团队、管理员全公司） */
async function searchAll(q: string, signal: AbortSignal): Promise<SearchResult> {
  const params = { q, page_size: LIMIT }
  const [c, o, qt] = await Promise.all([
    api.get<{ items: { id: string; name: string; industry: string | null; owner: Brief }[] }>(
      "/api/customers",
      params,
      signal,
    ),
    api.get<{ items: { id: string; name: string; amount: number; customer: Brief }[] }>(
      "/api/opportunities",
      params,
      signal,
    ),
    api.get<{ items: { id: string; code: string; total_price: number; tier_name: string; customer: Brief }[] }>(
      "/api/quotes",
      params,
      signal,
    ),
  ])
  return {
    customers: c.items.map((x) => ({
      id: x.id,
      title: x.name,
      sub: [x.industry, x.owner?.name].filter(Boolean).join(" · "),
      href: `/customers/${encodeURIComponent(x.id)}`,
    })),
    opportunities: o.items.map((x) => ({
      id: x.id,
      title: x.name,
      sub: [x.customer?.name, formatFen(x.amount)].filter(Boolean).join(" · "),
      href: `/pipeline?opp=${encodeURIComponent(x.id)}`,
    })),
    quotes: qt.items.map((x) => ({
      id: x.id,
      title: x.code,
      sub: [x.customer?.name, x.tier_name, formatFen(x.total_price)].filter(Boolean).join(" · "),
      href: `/quotes/${encodeURIComponent(x.id)}`,
    })),
  }
}

const GROUPS = [
  { key: "customers", heading: "客户", icon: Building2 },
  { key: "opportunities", heading: "商机", icon: Target },
  { key: "quotes", heading: "报价单", icon: FileText },
] as const

/** Ctrl K 全局搜索：输入关键词查客户 / 商机 / 报价单，也可以跳转页面和快捷操作 */
export function CommandMenu({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const router = useRouter()
  const { role, solo } = useSession()
  const [text, setText] = useState("")
  const q = useDebounced(text.trim(), 250)

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

  const search = useQuery({
    queryKey: ["global-search", q],
    queryFn: ({ signal }) => searchAll(q, signal),
    enabled: open && q.length > 0,
    staleTime: 30_000,
  })

  // 关闭时清空输入，下次打开从头开始
  const setOpen = (o: boolean) => {
    if (!o) setText("")
    onOpenChange(o)
  }
  const go = (href: string) => {
    setOpen(false)
    router.push(href)
  }

  const kw = text.trim().toLowerCase()
  const pages = navItemsFor(role, solo).filter((p) => !kw || p.label.toLowerCase().includes(kw))
  const actions = canCreateBusiness(role)
    ? [
        { label: "AI 出方案报价", href: "/ai", icon: Sparkles },
        { label: "新建客户", href: "/customers", icon: Plus },
        { label: "新建报销", href: "/expenses", icon: Receipt },
      ].filter((a) => !kw || a.label.toLowerCase().includes(kw))
    : []
  const data = q && search.data && q === text.trim() ? search.data : null
  const hits = data ? GROUPS.reduce((n, g) => n + data[g.key].length, 0) : 0
  const searching = kw.length > 0 && (search.isFetching || q !== text.trim())
  const nothing = kw.length > 0 && !searching && hits === 0 && pages.length === 0 && actions.length === 0

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="全局搜索" description="搜索客户、商机、报价单，或跳转页面">
      {/* 必须有 Command 根节点（之前缺了它，一打开就报错白屏）；结果来自服务端，不让 cmdk 再按文字过滤 */}
      <Command shouldFilter={false}>
        <CommandInput
          value={text}
          onValueChange={setText}
          placeholder="搜索客户、商机、报价单（名称或编号），或跳转页面…"
        />
        <CommandList>
          {searching ? (
            <div className="flex items-center gap-2 px-3 py-2 text-xs text-zinc-400">
              <Loader2 className="size-3.5 animate-spin" />
              正在搜索…
            </div>
          ) : null}
          {nothing ? <CommandEmpty>没有找到「{text.trim()}」相关的客户、商机或报价单</CommandEmpty> : null}
          {data
            ? GROUPS.map((g) =>
                data[g.key].length ? (
                  <CommandGroup key={g.key} heading={g.heading}>
                    {data[g.key].map((h) => (
                      <CommandItem key={h.id} value={`${g.key}-${h.id}`} onSelect={() => go(h.href)}>
                        <g.icon />
                        <span className="min-w-0 flex-1 truncate">{h.title}</span>
                        {h.sub ? (
                          <span className="max-w-[55%] shrink-0 truncate text-xs text-zinc-400">{h.sub}</span>
                        ) : null}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                ) : null,
              )
            : null}
          {hits ? <CommandSeparator /> : null}
          {actions.length ? (
            <CommandGroup heading="快捷操作">
              {actions.map((a) => (
                <CommandItem key={a.label} value={`action-${a.label}`} onSelect={() => go(a.href)}>
                  <a.icon className={a.icon === Sparkles ? "text-ai" : undefined} />
                  {a.label}
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}
          {pages.length ? (
            <CommandGroup heading="页面">
              {pages.map((p) => (
                <CommandItem key={p.href} value={`page-${p.href}`} onSelect={() => go(p.href)}>
                  <p.icon />
                  {p.label}
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}
        </CommandList>
      </Command>
    </CommandDialog>
  )
}
