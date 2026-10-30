"use client"

import { Loader2 } from "lucide-react"
import type { ReactNode } from "react"

import { useConfirmAction } from "@/components/biz/ConfirmAction"
import { SimpleSelect } from "@/components/biz/FormControls"
import { Warn, time } from "@/components/model-config/shared"
import { useSaveGroups, useSwitchEmbedding, type ModelCard, type ModelConfig } from "@/hooks/useModelConfig"
import { candidates, modelLabel, shortName } from "@/lib/model-config"

const NONE = "none"

function Row({ label, note, children }: { label: string; note?: ReactNode; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="text-sm font-medium">{label}</p>
      {children}
      {note ? <div className="text-xs text-zinc-500">{note}</div> : null}
    </div>
  )
}

const option = (m: ModelCard) => ({
  value: m.alias,
  label: `${modelLabel(m, m.alias)}${m.available ? "" : "（不可用）"}`,
})

/** 用哪个模型：对话、知识库、重排各选一个，改了立即生效。对话出错时自动换其他可用的 */
export function ModelUsage({ config }: { config: ModelConfig }) {
  const save = useSaveGroups()
  const switchTo = useSwitchEmbedding()
  const { ask, dialog } = useConfirmAction()
  const cards = new Map(config.models.map((m) => [m.alias, m]))
  const chat = config.groups["chat-agent"] ?? []
  const rerank = config.groups.rerank ?? []
  const embed = config.groups.embed?.[0] ?? ""
  const job = config.reindex
  const running = job.status === "running"
  const busy = save.isPending || switchTo.isPending || running

  // 选中的排第一，其余可用的对话模型按原顺序做备用
  const pickChat = (alias: string) => {
    const rest = [...chat, ...candidates(config, "chat").map((m) => m.alias)].filter(
      (a, i, all) => a !== alias && all.indexOf(a) === i,
    )
    save.mutate({ chat: [alias, ...rest], rerank })
  }
  const backups = chat
    .slice(1)
    .map((a) => cards.get(a))
    .filter((m) => m?.available)
    .map((m) => shortName(m!.provider))

  const embedOptions = candidates(config, "embedding")

  return (
    <div className="space-y-5">
      <Row label="对话" note={backups.length ? `出错时自动换：${[...new Set(backups)].join("、")}` : "没有备用模型"}>
        <SimpleSelect
          ariaLabel="对话模型"
          value={chat[0] ?? ""}
          placeholder="选择模型"
          disabled={busy}
          onChange={pickChat}
          options={candidates(config, "chat").map(option)}
        />
      </Row>
      <Row
        label="知识库"
        note={
          running ? (
            <span className="flex items-center gap-1.5">
              <Loader2 className="size-3.5 animate-spin" />
              正在换到 {job.target}：{job.done} / {job.total}
            </span>
          ) : job.status === "failed" ? (
            <Warn>
              换到 {job.target} 失败{job.at ? `（${time(job.at)}）` : ""}：{job.error}
            </Warn>
          ) : (
            "换模型会重新处理整个知识库"
          )
        }
      >
        <SimpleSelect
          ariaLabel="知识库模型"
          value={embed}
          placeholder="选择模型"
          disabled={busy}
          onChange={(alias) => {
            if (alias === embed) return
            ask({
              title: "换知识库模型？",
              description:
                `用 ${alias} 重新处理知识库的 ${config.kb_chunks} 段内容，` +
                `约调用 ${Math.ceil(config.kb_chunks / 10)} 次接口。完成后自动切换，失败不影响现在的使用。`,
              confirmLabel: "开始",
              onConfirm: () => switchTo.mutate(alias),
            })
          }}
          options={embedOptions.map(option)}
        />
      </Row>
      <Row label="重排" note="让知识库搜索结果更准，可以不用">
        <SimpleSelect
          ariaLabel="重排模型"
          value={rerank[0] ?? NONE}
          disabled={busy}
          onChange={(alias) => {
            const next = alias === NONE ? [] : [alias, ...rerank.filter((a) => a !== alias)]
            save.mutate({ chat, rerank: next })
          }}
          options={[{ value: NONE, label: "不使用" }, ...candidates(config, "rerank").map(option)]}
        />
      </Row>
      {dialog}
    </div>
  )
}
