"use client"

import { Plus, X } from "lucide-react"
import { useState } from "react"

import { FormSheet } from "@/components/biz/FormSheet"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { useSaveCompetitor, type Competitor, type CompetitorInput, type Objection } from "@/hooks/useCompetitors"
import { changedFrom } from "@/lib/form-dirty"

const lines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean)

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      {hint ? <span className="ml-2 text-xs text-zinc-400">{hint}</span> : null}
      {children}
    </label>
  )
}

/** 管理员新建 / 修改战卡：列表字段每行一条，常见说法逐条填写 */
export function CompetitorForm({
  open,
  onOpenChange,
  initial,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  initial: Competitor | null
}) {
  const save = useSaveCompetitor()
  const [name, setName] = useState(initial?.name ?? "")
  const [aliases, setAliases] = useState((initial?.aliases ?? []).join("、"))
  const [summary, setSummary] = useState(initial?.summary ?? "")
  const [strengths, setStrengths] = useState((initial?.strengths ?? []).join("\n"))
  const [weaknesses, setWeaknesses] = useState((initial?.weaknesses ?? []).join("\n"))
  const [tactics, setTactics] = useState((initial?.win_tactics ?? []).join("\n"))
  const [objections, setObjections] = useState<Objection[]>(initial?.objections ?? [{ say: "", respond: "" }])

  const dirty = changedFrom(
    [name, aliases, summary, strengths, weaknesses, tactics, objections],
    [
      initial?.name ?? "",
      (initial?.aliases ?? []).join("、"),
      initial?.summary ?? "",
      (initial?.strengths ?? []).join("\n"),
      (initial?.weaknesses ?? []).join("\n"),
      (initial?.win_tactics ?? []).join("\n"),
      initial?.objections ?? [{ say: "", respond: "" }],
    ],
  )

  const setObj = (i: number, patch: Partial<Objection>) =>
    setObjections((list) => list.map((o, j) => (j === i ? { ...o, ...patch } : o)))

  const submit = () => {
    const body: CompetitorInput = {
      name: name.trim(),
      aliases: aliases
        .split(/[、,，\s]+/)
        .map((s) => s.trim())
        .filter(Boolean),
      summary: summary.trim() || null,
      strengths: lines(strengths),
      weaknesses: lines(weaknesses),
      win_tactics: lines(tactics),
      objections: objections
        .map((o) => ({ say: o.say.trim(), respond: o.respond.trim() }))
        .filter((o) => o.say && o.respond),
    }
    save.mutate({ id: initial?.id, body }, { onSuccess: () => onOpenChange(false) })
  }

  return (
    <FormSheet
      open={open}
      onOpenChange={onOpenChange}
      dirty={dirty}
      wide
      title={initial ? `编辑战卡：${initial.name}` : "新建竞品战卡"}
      description="销售在商机里标注竞品后，可直接查看这里的应对话术；AI 工作台回答时也会引用。"
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={!name.trim() || save.isPending} onClick={submit}>
            保存
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="竞品名称">
          <Input value={name} maxLength={100} onChange={(e) => setName(e.target.value)} aria-label="竞品名称" />
        </Field>
        <Field label="别名" hint="客户口中的叫法，用顿号分隔，用于搜索">
          <Input value={aliases} onChange={(e) => setAliases(e.target.value)} aria-label="别名" />
        </Field>
        <Field label="一句话定位">
          <Input value={summary} maxLength={500} onChange={(e) => setSummary(e.target.value)} aria-label="一句话定位" />
        </Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="我们怎么赢" hint="每行一条">
            <Textarea rows={5} value={tactics} onChange={(e) => setTactics(e.target.value)} aria-label="我们怎么赢" />
          </Field>
          <Field label="他们的弱点" hint="每行一条">
            <Textarea
              rows={5}
              value={weaknesses}
              onChange={(e) => setWeaknesses(e.target.value)}
              aria-label="他们的弱点"
            />
          </Field>
          <Field label="他们的优势" hint="每行一条">
            <Textarea
              rows={5}
              value={strengths}
              onChange={(e) => setStrengths(e.target.value)}
              aria-label="他们的优势"
            />
          </Field>
        </div>
        <div className="space-y-2">
          <div className="text-sm font-medium">常见说法与应对</div>
          {objections.map((o, i) => (
            <div key={i} className="relative space-y-1.5 rounded-lg border border-zinc-200 p-2.5 pr-9">
              <Input
                value={o.say}
                maxLength={300}
                placeholder="客户 / 竞品的说法，例如：他们报价便宜一半"
                aria-label={`说法 ${i + 1}`}
                onChange={(e) => setObj(i, { say: e.target.value })}
              />
              <Textarea
                rows={2}
                value={o.respond}
                maxLength={1000}
                placeholder="我们的回应（销售可以直接照着说）"
                aria-label={`应对 ${i + 1}`}
                onChange={(e) => setObj(i, { respond: e.target.value })}
              />
              <Button
                size="icon-sm"
                variant="ghost"
                className="absolute top-2 right-1"
                aria-label={`删除第 ${i + 1} 条说法`}
                onClick={() => setObjections((list) => list.filter((_, j) => j !== i))}
              >
                <X />
              </Button>
            </div>
          ))}
          <Button
            size="xs"
            variant="outline"
            onClick={() => setObjections((list) => [...list, { say: "", respond: "" }])}
          >
            <Plus />
            添加一条
          </Button>
        </div>
      </div>
    </FormSheet>
  )
}
