"use client"

import { ArrowDown, ArrowUp, Loader2, RefreshCw, X } from "lucide-react"
import { useState } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { SimpleSelect } from "@/components/biz/FormControls"
import { Tag } from "@/components/biz/Tag"
import { Warn, time } from "@/components/model-config/shared"
import { Button } from "@/components/ui/button"
import { useSaveGroups, useSwitchEmbedding, type ModelCard, type ModelConfig } from "@/hooks/useModelConfig"
import { candidates, modelLabel, moveItem, sameList } from "@/lib/model-config"

function OrderedPicker({
  title,
  hint,
  list,
  onChange,
  options,
  cards,
  emptyText,
}: {
  title: string
  hint: string
  list: string[]
  onChange: (next: string[]) => void
  options: ModelCard[]
  cards: Map<string, ModelCard>
  emptyText: string
}) {
  const rest = options.filter((m) => !list.includes(m.alias))
  return (
    <div className="space-y-2">
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-zinc-500">{hint}</p>
      </div>
      {list.length === 0 ? <p className="text-xs text-zinc-400">{emptyText}</p> : null}
      <ol className="space-y-1">
        {list.map((alias, i) => {
          const card = cards.get(alias)
          return (
            <li key={alias} className="flex items-center gap-2 rounded-md border border-zinc-200 px-2 py-1.5 text-sm">
              <span className="w-10 shrink-0 text-xs text-zinc-400">{i === 0 ? "主用" : `备用 ${i}`}</span>
              <span className="min-w-0 flex-1 truncate">{modelLabel(card, alias)}</span>
              {card && !card.available ? <Tag color="yellow">不可用</Tag> : null}
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label={`上移 ${alias}`}
                disabled={i === 0}
                onClick={() => onChange(moveItem(list, i, -1))}
              >
                <ArrowUp />
              </Button>
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label={`下移 ${alias}`}
                disabled={i === list.length - 1}
                onClick={() => onChange(moveItem(list, i, 1))}
              >
                <ArrowDown />
              </Button>
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label={`移除 ${alias}`}
                onClick={() => onChange(list.filter((a) => a !== alias))}
              >
                <X />
              </Button>
            </li>
          )
        })}
      </ol>
      {rest.length ? (
        <SimpleSelect
          size="sm"
          className="sm:w-80"
          ariaLabel={`添加${title}`}
          value=""
          placeholder="添加模型…"
          onChange={(alias) => onChange([...list, alias])}
          options={rest.map((m) => ({
            value: m.alias,
            label: `${modelLabel(m, m.alias)}${m.available ? "" : "（不可用）"}`,
          }))}
        />
      ) : null}
    </div>
  )
}

function EmbeddingSwitch({ config, cards }: { config: ModelConfig; cards: Map<string, ModelCard> }) {
  const switchTo = useSwitchEmbedding()
  const { ask, dialog } = useConfirmAction()
  const current = config.groups.embed?.[0] ?? null
  const options = candidates(config, "embedding").filter((m) => m.alias !== current)
  const [target, setTarget] = useState("")
  const job = config.reindex
  const running = job.status === "running"
  const pick = cards.get(target)

  return (
    <div className="space-y-2">
      <div>
        <p className="text-sm font-medium">知识库</p>
        <p className="text-xs text-zinc-500">换模型要把知识库全部重新处理一遍，完成后才切换。</p>
      </div>
      <p className="text-sm">
        当前：{current ? modelLabel(cards.get(current), current) : "未配置"}
        {current && cards.get(current) && !cards.get(current)?.available ? (
          <span className="ml-2">
            <Tag color="yellow">不可用</Tag>
          </span>
        ) : null}
      </p>
      {running ? (
        <div className="space-y-1" role="status" aria-label="重建进度">
          <p className="flex items-center gap-1.5 text-xs text-zinc-600">
            <Loader2 className="size-3.5 animate-spin" />
            正在换到 {job.target}：{job.done} / {job.total}
          </p>
          <div className="h-1.5 overflow-hidden rounded bg-zinc-100">
            <div
              className="h-full bg-blue-500 transition-all"
              style={{ width: `${job.total ? Math.round((job.done / job.total) * 100) : 0}%` }}
            />
          </div>
        </div>
      ) : job.status === "failed" ? (
        <Warn>
          换到 {job.target} 失败{job.at ? `（${time(job.at)}）` : ""}：{job.error}
        </Warn>
      ) : job.status === "done" && job.at ? (
        <p className="text-xs text-emerald-700">
          {job.by ? `${job.by} ` : ""}
          {time(job.at)} 切换到 {job.target}，重建了 {job.total} 段。
        </p>
      ) : null}
      {options.length ? (
        <div className="flex flex-col gap-2 sm:flex-row">
          <SimpleSelect
            size="sm"
            className="sm:w-80"
            ariaLabel="新的向量模型"
            value={target}
            placeholder="换成…"
            disabled={running}
            onChange={setTarget}
            options={options.map((m) => ({
              value: m.alias,
              label: `${modelLabel(m, m.alias)}${m.available ? "" : "（不可用）"}`,
            }))}
          />
          <Button
            variant="outline"
            size="sm"
            disabled={!pick || !pick.available || running || switchTo.isPending}
            onClick={() =>
              ask({
                title: "换知识库模型？",
                description:
                  `用 ${pick?.alias} 重新处理知识库的 ${config.kb_chunks} 段内容，` +
                  `约调用 ${Math.ceil(config.kb_chunks / 10)} 次接口。完成后自动切换，失败不影响现在的使用。`,
                confirmLabel: "开始",
                onConfirm: () => switchTo.mutate(target, { onSuccess: () => setTarget("") }),
              })
            }
          >
            <RefreshCw />
            切换
          </Button>
        </div>
      ) : (
        <p className="text-xs text-zinc-400">
          没有其他可选的模型（需要 {config.embedding_dims} 维的 Embedding 模型）。
        </p>
      )}
      {dialog}
    </div>
  )
}

/** 默认模型：对话、重排的主用 + 备用顺序（出错时按顺序切换），知识库向量单独切换 */
export function DefaultModels({ config }: { config: ModelConfig }) {
  const save = useSaveGroups()
  const cards = new Map(config.models.map((m) => [m.alias, m]))
  const saved = { chat: config.groups["chat-agent"] ?? [], rerank: config.groups.rerank ?? [] }
  const [chat, setChat] = useState(saved.chat)
  const [rerank, setRerank] = useState(saved.rerank)
  const dirty = !sameList(chat, saved.chat) || !sameList(rerank, saved.rerank)
  const defaults = { chat: config.group_defaults["chat-agent"] ?? [], rerank: config.group_defaults.rerank ?? [] }
  const isDefault = sameList(chat, defaults.chat) && sameList(rerank, defaults.rerank)

  return (
    <div className="space-y-5 rounded-lg border border-zinc-200 p-4">
      <OrderedPicker
        title="对话"
        hint="出错时按顺序换下一个。只能选支持工具调用的模型。"
        list={chat}
        onChange={setChat}
        options={candidates(config, "chat")}
        cards={cards}
        emptyText="至少选一个"
      />
      <OrderedPicker
        title="重排"
        hint="让知识库检索结果更准。可以不选。"
        list={rerank}
        onChange={setRerank}
        options={candidates(config, "rerank")}
        cards={cards}
        emptyText="不使用"
      />
      <div className="flex flex-wrap justify-end gap-2">
        {!isDefault && defaults.chat.length ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setChat(defaults.chat)
              setRerank(defaults.rerank)
            }}
          >
            恢复默认
          </Button>
        ) : null}
        {dirty ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setChat(saved.chat)
              setRerank(saved.rerank)
            }}
          >
            撤销修改
          </Button>
        ) : null}
        <Button
          size="sm"
          disabled={!dirty || chat.length === 0 || save.isPending}
          onClick={() =>
            save.mutate(
              { chat, rerank },
              {
                onSuccess: (data) => {
                  setChat(data.groups["chat-agent"] ?? [])
                  setRerank(data.groups.rerank ?? [])
                },
              },
            )
          }
        >
          保存
        </Button>
      </div>
      <div className="border-t border-zinc-100 pt-4">
        <EmbeddingSwitch config={config} cards={cards} />
      </div>
    </div>
  )
}
