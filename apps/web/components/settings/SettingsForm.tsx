"use client"

import { Pencil, Plus, RotateCcw, X } from "lucide-react"
import { useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { useUpdateSettings } from "@/hooks/useSettings"
import { formatRelative } from "@/lib/format"
import {
  formatSetting,
  parseInputText,
  toInputText,
  validateStages,
  type PaymentStageValue,
  type SettingValue,
  type SettingsOut,
} from "@/lib/settings"
import { cn } from "@/lib/utils"

/** 回款计划：每期名称 / 比例 / 到期天数，可增删，底部显示比例合计 */
function StagesEditor({ value, onChange }: { value: PaymentStageValue[]; onChange: (v: PaymentStageValue[]) => void }) {
  const set = (i: number, patch: Partial<PaymentStageValue>) =>
    onChange(value.map((s, j) => (j === i ? { ...s, ...patch } : s)))
  const total = Math.round(value.reduce((n, s) => n + (Number.isFinite(s.ratio) ? s.ratio : 0), 0) * 10000) / 100
  return (
    <div className="space-y-2">
      {value.map((s, i) => (
        <div
          key={i}
          className="flex flex-wrap items-center gap-2 rounded-md border border-zinc-100 p-2 sm:border-0 sm:p-0"
        >
          <Input
            aria-label={`第 ${i + 1} 期名称`}
            value={s.name}
            maxLength={20}
            className="h-8 w-full sm:w-28"
            onChange={(e) => set(i, { name: e.target.value })}
          />
          <div className="flex items-center gap-1">
            <Input
              aria-label={`第 ${i + 1} 期比例`}
              inputMode="decimal"
              value={Number.isFinite(s.ratio) ? String(Math.round(s.ratio * 10000) / 100) : ""}
              className="h-8 w-16 text-right"
              onChange={(e) => set(i, { ratio: Number(e.target.value) / 100 })}
            />
            <span className="text-zinc-500">%</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-zinc-500">签订后</span>
            <Input
              aria-label={`第 ${i + 1} 期到期天数`}
              inputMode="numeric"
              value={String(s.due_days)}
              className="h-8 w-16 text-right"
              onChange={(e) => set(i, { due_days: Number(e.target.value) })}
            />
            <span className="text-zinc-500">天</span>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`删除第 ${i + 1} 期`}
            disabled={value.length <= 1}
            onClick={() => onChange(value.filter((_, j) => j !== i))}
          >
            <X />
          </Button>
        </div>
      ))}
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="xs"
          disabled={value.length >= 6}
          onClick={() => onChange([...value, { name: "", ratio: 0, due_days: 0 }])}
        >
          <Plus />
          加一期
        </Button>
        <span className={cn("text-xs", total === 100 ? "text-zinc-500" : "text-amber-600")}>合计 {total}%</span>
      </div>
    </div>
  )
}

function FieldInput({
  field,
  text,
  stages,
  onText,
  onStages,
}: {
  field: SettingValue
  text: string
  stages: PaymentStageValue[]
  onText: (t: string) => void
  onStages: (s: PaymentStageValue[]) => void
}) {
  if (field.kind === "stages") return <StagesEditor value={stages} onChange={onStages} />
  if (field.kind === "bool")
    return (
      <div className="flex justify-end">
        <Switch
          aria-label={field.label}
          checked={text === "true"}
          onCheckedChange={(on) => onText(on ? "true" : "false")}
        />
      </div>
    )
  const wide = field.kind === "cities" || field.kind === "percent_list"
  const suffix =
    field.kind === "percent" || field.kind === "percent_list" ? "%" : field.kind === "money" ? "元" : field.unit
  return (
    <div className={cn("flex items-center gap-1.5", wide ? "" : "justify-end")}>
      <Input
        aria-label={field.label}
        value={text}
        inputMode={wide ? "text" : "decimal"}
        placeholder={field.kind === "cities" ? "用顿号分隔，如 北京、上海" : undefined}
        className={cn("h-8", wide ? "w-full max-w-72" : "w-28 text-right")}
        onChange={(e) => onText(e.target.value)}
      />
      {suffix ? (
        <span className="shrink-0 text-zinc-500">{field.kind === "money" ? field.unit || "元" : suffix}</span>
      ) : null}
    </div>
  )
}

/** 一组配置：查看 ↔ 编辑；只提交改过的项 */
function SettingsGroup({ packId, name, fields }: { packId: string | null; name: string; fields: SettingValue[] }) {
  const update = useUpdateSettings(packId)
  const { ask, dialog } = useConfirmAction()
  const [editing, setEditing] = useState(false)
  const [texts, setTexts] = useState<Record<string, string>>({})
  const [stages, setStages] = useState<Record<string, PaymentStageValue[]>>({})
  const [error, setError] = useState<string | null>(null)

  const start = () => {
    setTexts(Object.fromEntries(fields.map((f) => [f.key, toInputText(f.kind, f.value)])))
    setStages(
      Object.fromEntries(
        fields.filter((f) => f.kind === "stages").map((f) => [f.key, structuredClone(f.value as PaymentStageValue[])]),
      ),
    )
    setError(null)
    setEditing(true)
  }

  const save = () => {
    const values: Record<string, unknown> = {}
    for (const f of fields) {
      if (f.kind === "stages") {
        const v = stages[f.key] ?? []
        const err = validateStages(v)
        if (err) return setError(`「${f.label}」：${err}`)
        if (JSON.stringify(v) !== JSON.stringify(f.value)) values[f.key] = v
        continue
      }
      const text = texts[f.key] ?? ""
      if (text === toInputText(f.kind, f.value)) continue
      const parsed = parseInputText(f, text)
      if (!parsed.ok) return setError(parsed.error)
      values[f.key] = parsed.value
    }
    if (Object.keys(values).length === 0) return setEditing(false)
    update.mutate({ values }, { onSuccess: () => setEditing(false) })
  }

  const reset = (f: SettingValue) =>
    ask({
      title: "恢复默认值",
      description: `「${f.label}」将恢复为 ${formatSetting(f.kind, f.default, f.unit)}，立即生效。`,
      confirmLabel: "恢复默认",
      onConfirm: () => update.mutate({ values: { [f.key]: null } }),
    })

  return (
    <section aria-label={name} className="rounded-lg border border-zinc-200">
      <div className="flex min-h-12 items-center justify-between gap-3 border-b border-zinc-100 py-2 pr-2 pl-4">
        <div className="min-w-0">
          <h3 className="font-medium">{name}</h3>
          {GROUP_HELP[name] ? <p className="mt-0.5 text-xs text-zinc-400">{GROUP_HELP[name]}</p> : null}
        </div>
        {editing ? null : (
          <Button variant="outline" size="xs" onClick={start} aria-label={`编辑${name}`} className="shrink-0">
            <Pencil />
            编辑
          </Button>
        )}
      </div>
      <dl className="divide-y divide-zinc-100">
        {fields.map((f) => {
          // 回款计划、城市列表这类长内容放到标签下面整行显示；数字类靠右对齐成一列
          const wide = f.kind === "stages" || (editing && (f.kind === "cities" || f.kind === "percent_list"))
          return (
            <div
              key={f.key}
              className={cn("px-4 py-3", wide ? "space-y-2" : "flex items-start justify-between gap-x-6 gap-y-1")}
            >
              <dt className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="break-words text-zinc-800">{f.label}</span>
                  {f.overridden ? (
                    <span
                      className="rounded bg-amber-50 px-1.5 text-[11px] leading-5 text-amber-700"
                      title={[f.updated_by, f.updated_at ? formatRelative(f.updated_at) : null]
                        .filter(Boolean)
                        .join(" · ")}
                    >
                      已修改
                    </span>
                  ) : null}
                </div>
                {f.help ? <div className="mt-0.5 text-xs break-words text-zinc-400">{f.help}</div> : null}
              </dt>
              <dd className={cn("min-w-0", wide ? "" : "max-w-[55%] shrink-0 text-right")}>
                {editing ? (
                  <FieldInput
                    field={f}
                    text={texts[f.key] ?? ""}
                    stages={stages[f.key] ?? []}
                    onText={(t) => setTexts((s) => ({ ...s, [f.key]: t }))}
                    onStages={(v) => setStages((s) => ({ ...s, [f.key]: v }))}
                  />
                ) : (
                  <>
                    {f.kind === "stages" && Array.isArray(f.value) ? (
                      <StagesView value={f.value as PaymentStageValue[]} />
                    ) : (
                      <div className="font-medium break-words tabular-nums">
                        {formatSetting(f.kind, f.value, f.unit)}
                      </div>
                    )}
                    {f.overridden ? (
                      <div className={cn("mt-0.5 text-xs text-zinc-400", wide ? "" : "text-right")}>
                        默认 {formatSetting(f.kind, f.default, f.unit)}
                        <button
                          type="button"
                          className="ml-2 inline-flex items-center gap-0.5 text-zinc-600 hover:text-zinc-900 hover:underline"
                          onClick={() => reset(f)}
                          disabled={update.isPending}
                        >
                          <RotateCcw className="size-3" />
                          恢复默认
                        </button>
                      </div>
                    ) : null}
                  </>
                )}
              </dd>
            </div>
          )
        })}
      </dl>
      {editing ? (
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-zinc-100 px-4 py-3">
          {error ? (
            <span role="alert" className="mr-auto text-sm text-red-600">
              {error}
            </span>
          ) : null}
          <Button variant="outline" size="sm" onClick={() => setEditing(false)} disabled={update.isPending}>
            取消
          </Button>
          <Button size="sm" onClick={save} disabled={update.isPending}>
            保存
          </Button>
        </div>
      ) : null}
      {dialog}
    </section>
  )
}

/** 回款计划只读：每期一行 */
function StagesView({ value }: { value: PaymentStageValue[] }) {
  return (
    <ol className="divide-y divide-zinc-100 rounded-md border border-zinc-100 bg-zinc-50/50">
      {value.map((s, i) => (
        <li key={i} className="flex items-center gap-3 px-3 py-1.5">
          <span className="w-5 shrink-0 text-xs text-zinc-400 tabular-nums">{i + 1}</span>
          <span className="min-w-0 flex-1 truncate">{s.name}</span>
          <span className="w-12 text-right font-medium tabular-nums">{Math.round(s.ratio * 10000) / 100}%</span>
          <span className="w-24 text-right text-xs text-zinc-500">
            {s.due_days === 0 ? "签订当天" : `签订后 ${s.due_days} 天`}
          </span>
        </li>
      ))}
    </ol>
  )
}

/** 分组的一句话说明（通用规则页、行业包参数共用） */
const GROUP_HELP: Record<string, string> = {
  报价与审批: "报价在什么情况下需要主管审批",
  提成: "合同签订后提成怎么算",
  报销: "报销标准，超出标准需要审批",
  商机: "各阶段默认赢率和停滞提醒",
  回款: "合同生成时怎么拆回款期次，逾期怎么处理",
  票据: "报销票据的上传限制",
  "AI 助手": "AI 出方案时的重新配置次数与工具调用上限",
  报价: "本行业单独的毛利底线和经济版折扣",
  选型: "AI 估算硬件配置时用到的参数",
}

/** 某一组的配置卡片（业务规则页按组切换显示） */
export function SettingsGroupCard({
  packId,
  data,
  group,
}: {
  packId: string | null
  data: SettingsOut
  group: string
}) {
  return (
    <SettingsGroup key={group} packId={packId} name={group} fields={data.fields.filter((f) => f.group === group)} />
  )
}

/** 按分组展示的配置表单（通用规则页、行业包「业务规则」共用） */
export function SettingsForm({ packId, data }: { packId: string | null; data: SettingsOut }) {
  return (
    <div className="space-y-4">
      {data.groups.map((g) => (
        <SettingsGroup key={g} packId={packId} name={g} fields={data.fields.filter((f) => f.group === g)} />
      ))}
    </div>
  )
}
