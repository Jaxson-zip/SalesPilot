"use client"

import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

/**
 * 下划线标签栏（记录页 / 审批中心共用）：栏高 40px 与 ViewBar 一致；
 * 标签 28px 高、底部对齐，上方留白约 7px（与 ViewBar 按钮基本一致），下划线压在栏的底边上。
 */
export const LINE_TABS_LIST =
  "h-10! w-full shrink-0 items-end justify-start gap-0.5 border-b border-zinc-200 px-3 py-0! sm:gap-1"
export const LINE_TABS_TRIGGER = "group mb-1 h-7! flex-none rounded-md px-2 hover:bg-zinc-100"

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
      <TabsList variant="line" className={LINE_TABS_LIST}>
        {tabs.map((t) => (
          <TabsTrigger key={t.value} value={t.value} title={t.label} className={LINE_TABS_TRIGGER}>
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
