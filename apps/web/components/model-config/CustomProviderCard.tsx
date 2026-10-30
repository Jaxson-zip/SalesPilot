"use client"

import { Loader2, Pencil, PlugZap, Plus, Trash2, X } from "lucide-react"
import { useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { FormField, SimpleSelect } from "@/components/biz/FormControls"
import { AvailTag, ModelChip, Warn, time } from "@/components/model-config/shared"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import {
  useDeleteCustom,
  useSaveCustom,
  useTestCustom,
  type CustomInput,
  type CustomModelInput,
  type CustomProvider,
  type LinkType,
  type ModelCapabilities,
  type ModelKind,
  type ModelTestResult,
} from "@/hooks/useModelConfig"
import { CUSTOM_PRESETS, CUSTOM_PROTOCOLS, LINK_LABELS, customAlias, suggestId, validId } from "@/lib/model-config"

interface Row extends CustomModelInput {
  /** 本次测试结果（不保存） */
  result?: ModelTestResult
}

interface Form {
  id: string
  name: string
  protocol: LinkType
  adapter: string
  api_base: string
  key: string
  models: Row[]
}

const KINDS: { value: ModelKind; label: string }[] = [
  { value: "chat", label: "对话" },
  { value: "embedding", label: "向量（Embedding）" },
  { value: "rerank", label: "重排（Rerank）" },
]

const CAPS: { key: keyof ModelCapabilities; label: string }[] = [
  { key: "tools", label: "工具调用" },
  { key: "stream", label: "流式输出" },
  { key: "stream_tools", label: "流式工具调用" },
  { key: "json_mode", label: "JSON 模式" },
]

const emptyRow = (): Row => ({ model: "", kind: "chat", capabilities: { tools: false, stream: true } })

function initial(p?: CustomProvider): Form {
  if (!p)
    return { id: "", name: "", protocol: "openai_compat", adapter: "", api_base: "", key: "", models: [emptyRow()] }
  return {
    id: p.id,
    name: p.name,
    protocol: p.protocol,
    adapter: p.adapter,
    api_base: p.api_base,
    key: "",
    models: p.models.map((m) => ({ model: m.model, kind: m.kind, capabilities: { ...m.capabilities } })),
  }
}

function ModelRow({
  row,
  index,
  dims,
  testing,
  canTest,
  onChange,
  onRemove,
  onTest,
}: {
  row: Row
  index: number
  dims: number
  testing: boolean
  canTest: boolean
  onChange: (r: Row) => void
  onRemove?: () => void
  onTest: () => void
}) {
  const caps = row.capabilities
  const setCap = (key: keyof ModelCapabilities, v: boolean) => onChange({ ...row, capabilities: { ...caps, [key]: v } })
  return (
    <div className="space-y-2 rounded-md border border-zinc-100 bg-zinc-50/60 p-3">
      <div className="grid gap-2 sm:grid-cols-[1fr_11rem_auto]">
        <Input
          aria-label={`模型 ${index + 1} 名称`}
          value={row.model}
          onChange={(e) => onChange({ ...row, model: e.target.value, result: undefined })}
          placeholder="上游模型名，以厂商文档为准"
        />
        <SimpleSelect
          ariaLabel={`模型 ${index + 1} 用途`}
          value={row.kind}
          onChange={(kind) => onChange({ ...row, kind, result: undefined })}
          options={KINDS}
        />
        <div className="flex gap-1">
          <Button
            variant="outline"
            size="sm"
            disabled={testing || !canTest || !row.model.trim()}
            title={canTest ? undefined : "先填写厂商标识"}
            onClick={onTest}
          >
            {testing ? <Loader2 className="animate-spin" /> : <PlugZap />}
            测试
          </Button>
          {onRemove ? (
            <Button variant="ghost" size="icon-sm" aria-label={`删除模型 ${index + 1}`} onClick={onRemove}>
              <X />
            </Button>
          ) : null}
        </div>
      </div>
      {row.kind === "chat" ? (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-600">
          {CAPS.map((c) => (
            <label key={c.key} className="inline-flex items-center gap-1.5">
              <Checkbox checked={Boolean(caps[c.key])} onCheckedChange={(v) => setCap(c.key, v === true)} />
              {c.label}
            </label>
          ))}
          <span className="text-zinc-400">点「测试」自动检测；不支持工具调用的不能用作 AI 助手</span>
        </div>
      ) : row.kind === "embedding" ? (
        <p className="text-xs text-zinc-500">
          {caps.dims
            ? caps.dims === dims
              ? `向量维度 ${caps.dims}，可以用于知识库`
              : `向量维度 ${caps.dims}，知识库需要 ${dims} 维，不能用于知识库`
            : "点「测试」检测向量维度"}
        </p>
      ) : null}
      {row.result ? (
        row.result.ok ? (
          <p className="text-xs text-emerald-700">连接成功</p>
        ) : (
          <Warn>连接失败：{row.result.error ?? "未知错误"}</Warn>
        )
      ) : null}
    </div>
  )
}

/** 自定义厂商：新建（p 为空）或修改。标识建好后不能改（模型别名以它为前缀） */
function CustomForm({
  p,
  dims,
  embedAlias,
  onDone,
}: {
  p?: CustomProvider
  dims: number
  embedAlias: string | null
  onDone: () => void
}) {
  const save = useSaveCustom()
  const test = useTestCustom()
  const remove = useDeleteCustom()
  const { ask, dialog } = useConfirmAction()
  const [form, setForm] = useState<Form>(() => initial(p))
  const [testing, setTesting] = useState<number | null>(null)
  const set = (patch: Partial<Form>) => setForm((f) => ({ ...f, ...patch }))
  const setRow = (i: number, row: Row) => set({ models: form.models.map((r, j) => (j === i ? row : r)) })
  const isNew = !p
  const id = form.id.trim()
  const typed = form.key.trim()
  const preset = CUSTOM_PRESETS.find((x) => x.id === id && x.base === form.api_base)
  const inUse = embedAlias && id && embedAlias.startsWith(`${id}-`)
  const named = form.models.filter((m) => m.model.trim())
  const canSave =
    validId(id) &&
    form.name.trim() !== "" &&
    named.length > 0 &&
    (form.protocol === "native" || form.api_base.trim() !== "") &&
    !save.isPending

  const runTest = (i: number) => {
    const row = form.models[i]
    setTesting(i)
    test.mutate(
      {
        id,
        body: {
          protocol: form.protocol,
          adapter: form.adapter.trim(),
          api_base: form.api_base.trim(),
          key: typed || null,
          model: { model: row.model.trim(), kind: row.kind, capabilities: row.capabilities },
          detect: true,
        },
      },
      {
        onSuccess: (r) => {
          const caps = { ...row.capabilities, ...(r.capabilities ?? {}) }
          if (r.dims) caps.dims = r.dims
          setRow(i, { ...row, capabilities: r.ok ? caps : row.capabilities, result: r })
        },
        onSettled: () => setTesting(null),
      },
    )
  }

  const submit = () => {
    const body: CustomInput = {
      name: form.name.trim(),
      protocol: form.protocol,
      adapter: form.protocol === "native" ? form.adapter.trim() : "",
      api_base: form.api_base.trim(),
      key: typed || null,
      models: named.map((m) => ({ model: m.model.trim(), kind: m.kind, capabilities: m.capabilities })),
    }
    save.mutate({ id, body }, { onSuccess: onDone })
  }

  return (
    <div className="space-y-3">
      {isNew ? (
        <FormField label="从常用厂商填入" hint={preset?.hint ?? "也可以不选，直接填写下面的内容"}>
          <SimpleSelect
            ariaLabel="常用厂商"
            value={preset?.id ?? ""}
            placeholder="选择厂商（可选）"
            onChange={(v) => {
              const hit = CUSTOM_PRESETS.find((x) => x.id === v)
              if (hit) set({ id: hit.id, name: hit.name, api_base: hit.base, protocol: "openai_compat" })
            }}
            options={CUSTOM_PRESETS.map((x) => ({ value: x.id, label: x.name }))}
          />
        </FormField>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <FormField label="名称" required htmlFor="custom-name">
          <Input
            id="custom-name"
            value={form.name}
            onChange={(e) =>
              set({ name: e.target.value, ...(isNew && !form.id ? { id: suggestId(e.target.value) } : {}) })
            }
            placeholder="例如 Kimi"
          />
        </FormField>
        <FormField
          label="标识"
          required
          htmlFor="custom-id"
          hint={isNew ? "小写字母、数字、短横线；模型在系统里显示为「标识-模型名」，建好后不能改" : "建好后不能改"}
          error={id && !validId(id) ? "2～24 位，小写字母开头，只能有小写字母、数字和短横线" : undefined}
        >
          <Input
            id="custom-id"
            value={form.id}
            disabled={!isNew}
            onChange={(e) => set({ id: e.target.value.toLowerCase() })}
            placeholder="kimi"
          />
        </FormField>
        <FormField label="协议">
          <SimpleSelect
            ariaLabel="协议"
            value={form.protocol}
            onChange={(v) => set({ protocol: v })}
            options={CUSTOM_PROTOCOLS}
          />
        </FormField>
        {form.protocol === "native" ? (
          <FormField label="适配名" htmlFor="custom-adapter" hint="LiteLLM 的厂商名，例如 moonshot、zhipuai、ollama">
            <Input
              id="custom-adapter"
              value={form.adapter}
              onChange={(e) => set({ adapter: e.target.value })}
              placeholder="moonshot"
            />
          </FormField>
        ) : null}
        <FormField
          label="接口地址"
          required={form.protocol === "openai_compat"}
          htmlFor="custom-base"
          hint={form.protocol === "native" ? "原生适配一般不用填" : "一般以 /v1 结尾，以厂商文档为准"}
        >
          <Input
            id="custom-base"
            value={form.api_base}
            onChange={(e) => set({ api_base: e.target.value })}
            placeholder="https://…/v1"
          />
        </FormField>
        <FormField label="API Key" htmlFor="custom-key">
          <Input
            id="custom-key"
            type="password"
            autoComplete="off"
            value={form.key}
            onChange={(e) => set({ key: e.target.value })}
            placeholder={
              p?.has_key && !p.broken
                ? `已保存${p.tail ? `（末 4 位 ${p.tail}）` : ""}，如需更换粘贴新的`
                : "粘贴 API Key"
            }
          />
        </FormField>
      </div>
      {p?.broken ? <Warn>之前保存的 Key 解不开了（服务器的加密密钥换过），请重新填写。</Warn> : null}
      <div className="space-y-2">
        <p className="text-sm font-medium">模型</p>
        {form.models.map((row, i) => (
          <ModelRow
            key={i}
            row={row}
            index={i}
            dims={dims}
            testing={testing === i}
            canTest={validId(id) && testing === null}
            onChange={(r) => setRow(i, r)}
            onRemove={form.models.length > 1 ? () => set({ models: form.models.filter((_, j) => j !== i) }) : undefined}
            onTest={() => runTest(i)}
          />
        ))}
        {validId(id) && named.length ? (
          <p className="text-xs text-zinc-400">系统里的名字：{named.map((m) => customAlias(id, m.model)).join("、")}</p>
        ) : null}
        <Button
          variant="ghost"
          size="sm"
          disabled={form.models.length >= 20}
          onClick={() => set({ models: [...form.models, emptyRow()] })}
        >
          <Plus />
          添加模型
        </Button>
      </div>
      <div className="flex flex-wrap justify-end gap-2">
        {p ? (
          <Button
            variant="ghost"
            size="sm"
            className="mr-auto text-red-600"
            disabled={remove.isPending || Boolean(inUse)}
            title={inUse ? "知识库正在用这个厂商的向量模型，先换掉再删除" : undefined}
            onClick={() =>
              ask({
                title: `删除「${p.name}」？`,
                description: "删除后它的模型不再可用；默认模型里用到的会自动去掉，排在后面的备用模型顶上。",
                confirmLabel: "删除",
                destructive: true,
                onConfirm: () => remove.mutate(p.id, { onSuccess: onDone }),
              })
            }
          >
            <Trash2 />
            删除厂商
          </Button>
        ) : null}
        <Button variant="ghost" size="sm" onClick={onDone}>
          取消
        </Button>
        <Button size="sm" disabled={!canSave} onClick={submit}>
          保存
        </Button>
      </div>
      {dialog}
    </div>
  )
}

export function CustomProviderCard({
  p,
  dims,
  embedAlias,
  onClose,
}: {
  p?: CustomProvider
  dims: number
  embedAlias: string | null
  /** 新建表单的「取消」/ 保存后关闭 */
  onClose?: () => void
}) {
  const [editing, setEditing] = useState(!p)
  const done = () => (p ? setEditing(false) : onClose?.())
  return (
    <section aria-label={p ? p.name : "新增厂商"} className="space-y-3 rounded-lg border border-zinc-200 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium">{p ? p.name : "新增厂商"}</h3>
        {p ? (
          <>
            <AvailTag available={p.available} configured={p.has_key && !p.broken} />
            <span className="text-xs text-zinc-400">
              {p.id} · {LINK_LABELS[p.protocol]}
              {p.adapter ? `（${p.adapter}）` : ""}
              {p.saved_by && p.saved_at ? ` · ${p.saved_by} ${time(p.saved_at)} 保存` : ""}
            </span>
          </>
        ) : null}
        {p && !editing ? (
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setEditing(true)}>
            <Pencil />
            编辑
          </Button>
        ) : null}
      </div>
      {p && !editing ? (
        <div className="space-y-1 text-xs text-zinc-500">
          {p.api_base ? <p className="break-all">接口地址：{p.api_base}</p> : null}
          <div className="flex flex-wrap gap-1">
            {p.models.map((m) => (
              <ModelChip
                key={m.alias}
                m={{ alias: m.alias, kind: m.kind, available: m.available ?? false, tools: m.capabilities.tools }}
              />
            ))}
          </div>
          {p.broken ? <Warn>保存的 Key 解不开了（服务器的加密密钥换过），请编辑后重新填写。</Warn> : null}
          {!p.has_key ? <p>还没有填写 Key</p> : null}
        </div>
      ) : (
        <CustomForm p={p} dims={dims} embedAlias={embedAlias} onDone={done} />
      )}
    </section>
  )
}
