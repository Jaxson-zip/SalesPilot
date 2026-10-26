"use client"

import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export interface RecordTab {
  value: string
  label: string
  icon: LucideIcon
  content: ReactNode
}

/**
 * 记录页右侧标签页（Twenty 下划线样式）。
 * 手机上未选中的标签只显示图标，选中的显示图标 + 文字，保证一行放得下。
 */
export function RecordTabs({
  tabs,
  value,
  onValueChange,
}: {
  tabs: RecordTab[]
  value: string
  onValueChange: (v: string) => void
}) {
  return (
    <Tabs value={value} onValueChange={onValueChange} className="flex min-h-0 flex-1 flex-col gap-0">
      <TabsList
        variant="line"
        className="h-10! w-full shrink-0 justify-start gap-0.5 border-b border-zinc-200 px-3 sm:gap-1"
      >
        {tabs.map((t) => (
          <TabsTrigger key={t.value} value={t.value} title={t.label} className="group flex-none px-2">
            <t.icon className="size-3.5" />
            <span className="max-sm:hidden max-sm:group-data-[state=active]:inline">{t.label}</span>
          </TabsTrigger>
        ))}
      </TabsList>
      {tabs.map((t) => (
        <TabsContent key={t.value} value={t.value} className="p-4 sm:p-5 lg:min-h-0 lg:overflow-y-auto">
          {t.content}
        </TabsContent>
      ))}
    </Tabs>
  )
}
