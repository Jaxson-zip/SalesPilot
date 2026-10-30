"use client"

import { Loader2, PlugZap, Plus, X } from "lucide-react"
import { useState } from "react"

import { SimpleSelect } from "@/components/biz/FormControls"
import { Field, MoreSettings } from "@/components/model-config/ProviderRows"
import { Warn } from "@/components/model-config/shared"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import {
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
import { CUSTOM_PRESETS, CUSTOM_PROTOCOLS, customAlias, suggestId, validId } from "@/lib/model-config"

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
          <span className="text-zinc-400">点「测试」自动勾选</span>
        </div>
      ) : row.kind === "embedding" ? (
        <p className="text-xs text-zinc-500">
          {caps.dims
            ? caps.dims === dims
              ? `${caps.dims} 维，可用于知识库`
              : `${caps.dims} 维，知识库需要 ${dims} 维，不能用`
            : "点「测试」检测维度"}
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

/** 其他厂商的编辑区：新建（p 为空）或修改。标识建好后不能改（模型别名以它为前缀） */
export function CustomEditor({ p, dims, onDone }: { p?: CustomProvider; dims: number; onDone: () => void }) {
  const save = useSaveCustom()
  const test = useTestCustom()
  const [form, setForm] = useState<Form>(() => initial(p))
  const [testing, setTesting] = useState<number | null>(null)
  const set = (patch: Partial<Form>) => setForm((f) => ({ ...f, ...patch }))
  const setRow = (i: number, row: Row) => set({ models: form.models.map((r, j) => (j === i ? row : r)) })
  const isNew = !p
  const id = form.id.trim()
  const typed = form.key.trim()
  const preset = CUSTOM_PRESETS.find((x) => x.id === id && x.base === form.api_base)
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
        <Field label="厂商">
          <SimpleSelect
            ariaLabel="常用厂商"
            value={preset?.id ?? ""}
            placeholder="选择常用厂商，或直接填写"
            onChange={(v) => {
              const hit = CUSTOM_PRESETS.find((x) => x.id === v)
              if (hit) set({ id: hit.id, name: hit.name, api_base: hit.base, protocol: "openai_compat" })
            }}
            options={CUSTOM_PRESETS.map((x) => ({ value: x.id, label: x.name }))}
          />
        </Field>
      ) : null}
      {isNew && preset?.hint ? <p className="text-xs text-zinc-400">{preset.hint}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="名称">
          <Input
            value={form.name}
            onChange={(e) =>
              set({ name: e.target.value, ...(isNew && !form.id ? { id: suggestId(e.target.value) } : {}) })
            }
            placeholder="例如 Kimi"
          />
        </Field>
        <Field label="API Key">
          <Input
            type="password"
            autoComplete="off"
            value={form.key}
            onChange={(e) => set({ key: e.target.value })}
            placeholder={
              p?.has_key && !p.broken
                ? `已配置${p.tail ? `（末 4 位 ${p.tail}）` : ""}，输入新值可替换`
                : "输入 API Key"
            }
          />
        </Field>
      </div>
      {isNew ? (
        <Field label="标识（英文小写，建好后不能改）">
          <Input value={form.id} onChange={(e) => set({ id: e.target.value.toLowerCase() })} placeholder="例如 kimi" />
          {id && !validId(id) ? (
            <span className="text-xs text-red-600">2～24 位，小写字母开头，只能有小写字母、数字和短横线</span>
          ) : null}
        </Field>
      ) : null}
      <Field label="接口地址">
        <Input
          value={form.api_base}
          onChange={(e) => set({ api_base: e.target.value })}
          placeholder={form.protocol === "native" ? "原生适配一般不用填" : "https://…/v1"}
        />
      </Field>
      {p?.broken ? <Warn>之前保存的 Key 解不开了（服务器的加密密钥换过），请重新填写。</Warn> : null}
      <div className="space-y-2">
        <p className="text-xs text-zinc-500">模型</p>
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
      <MoreSettings>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="协议">
            <SimpleSelect
              ariaLabel="协议"
              value={form.protocol}
              onChange={(v) => set({ protocol: v })}
              options={CUSTOM_PROTOCOLS}
            />
          </Field>
          {form.protocol === "native" ? (
            <Field label="适配名">
              <Input value={form.adapter} onChange={(e) => set({ adapter: e.target.value })} placeholder="moonshot" />
            </Field>
          ) : null}
        </div>
      </MoreSettings>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onDone}>
          取消
        </Button>
        <Button size="sm" disabled={!canSave} onClick={submit}>
          保存
        </Button>
      </div>
    </div>
  )
}
