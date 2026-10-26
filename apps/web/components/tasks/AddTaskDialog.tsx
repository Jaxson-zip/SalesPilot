"use client"

import { useState } from "react"

import { DatePicker, FormField, SimpleSelect } from "@/components/biz/FormControls"
import { QuickChips } from "@/components/biz/QuickChips"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { useCreateTask } from "@/hooks/useTasks"
import { useTemplates } from "@/hooks/useTemplates"
import {
  DEFAULT_DUE_TIME,
  DUE_SHORTCUTS,
  dueShortcutDate,
  TASK_TYPE_OPTIONS,
  toDueIso,
  type DueShortcut,
} from "@/lib/tasks"
import { cn } from "@/lib/utils"
import type { TaskSubjectType, TaskType } from "@/types/api"

interface Draft {
  title: string
  type: TaskType
  date: string
  time: string
}

const emptyDraft = (): Draft => ({
  title: "",
  type: "call",
  date: dueShortcutDate("tomorrow"),
  time: DEFAULT_DUE_TIME,
})

/** 添加下一步（v3 §12）：标题、类型、到期日期 + 时间；快捷选项 今天 / 明天 / 下周一 */
export function AddTaskDialog({
  open,
  onOpenChange,
  subjectType,
  subjectId,
  subjectName,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  subjectType: TaskSubjectType
  subjectId: string
  subjectName: string
}) {
  const [d, setD] = useState<Draft>(emptyDraft)
  const [error, setError] = useState<string | null>(null)
  const create = useCreateTask()
  const quick = useTemplates().data?.task ?? []
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setD((p) => ({ ...p, [k]: v }))

  const close = () => {
    setD(emptyDraft())
    setError(null)
    onOpenChange(false)
  }
  const save = () => {
    const title = d.title.trim()
    const due = toDueIso(d.date, d.time)
    if (!title) return setError("请填写要做的事")
    if (!due) return setError("请选择到期日期和时间")
    setError(null)
    create.mutate(
      { title, due_at: due, type: d.type, subject_type: subjectType, subject_id: subjectId },
      { onSuccess: close },
    )
  }
  const active = (s: DueShortcut) => d.date === dueShortcutDate(s)

  return (
    <Dialog open={open} onOpenChange={(o) => !o && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>添加下一步</DialogTitle>
          <DialogDescription>{subjectName}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <FormField label="要做的事" required htmlFor="task-title" error={error ?? undefined}>
            <Input
              id="task-title"
              autoFocus
              maxLength={200}
              value={d.title}
              placeholder="例如：电话确认方案评审时间"
              onChange={(e) => set("title", e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && save()}
            />
          </FormField>
          <QuickChips
            label="常用下一步"
            items={quick.map((t) => ({ key: t.title, label: t.title }))}
            onPick={(title) => {
              const tpl = quick.find((t) => t.title === title)
              if (tpl) setD((p) => ({ ...p, title: tpl.title, type: tpl.type }))
            }}
          />
          <FormField label="类型" htmlFor="task-type">
            <SimpleSelect
              id="task-type"
              value={d.type}
              onChange={(t) => set("type", t)}
              options={TASK_TYPE_OPTIONS}
              ariaLabel="任务类型"
            />
          </FormField>
          <FormField label="到期时间" required>
            <div className="flex gap-1.5">
              {DUE_SHORTCUTS.map((s) => (
                <Button
                  key={s.value}
                  type="button"
                  size="xs"
                  variant="outline"
                  className={cn("h-7", active(s.value) && "border-zinc-900 bg-zinc-900 text-white hover:bg-zinc-800")}
                  aria-pressed={active(s.value)}
                  onClick={() => set("date", dueShortcutDate(s.value))}
                >
                  {s.label}
                </Button>
              ))}
            </div>
            <div className="grid grid-cols-[1fr_120px] gap-2">
              <DatePicker value={d.date} onChange={(v) => set("date", v)} ariaLabel="到期日期" />
              <Input
                id="task-time"
                type="time"
                aria-label="到期时间"
                value={d.time}
                onChange={(e) => set("time", e.target.value)}
              />
            </div>
          </FormField>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button onClick={save} disabled={create.isPending}>
            {create.isPending ? "添加中…" : "添加"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
