import { BomTable } from "@/components/agent/BomTable"
import { RequirementCard } from "@/components/agent/RequirementCard"
import { Sources } from "@/components/agent/Sources"
import { TierCards } from "@/components/agent/TierCards"
import type { AgentArtifact } from "@/lib/agent-reducer"
import { QuoteCard } from "@/components/agent/QuoteCard"
import { isCoreQuote, isCoreTier, isCoreTiers, toBomData, toTierCards } from "@/lib/artifacts"
import { isRequirementCard } from "@/lib/requirement-card"
import type { BomData, SolutionTier, SourceRef } from "@/types/api"

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null

function isTiers(v: unknown): v is SolutionTier[] {
  return Array.isArray(v) && v.every((t) => isObj(t) && typeof t.name === "string" && typeof t.price === "number")
}

function isBom(v: unknown): v is BomData {
  return isObj(v) && typeof v.title === "string" && Array.isArray(v.items) && Array.isArray(v.totals)
}

function isSources(v: unknown): v is SourceRef[] {
  return Array.isArray(v) && v.every((s) => isObj(s) && typeof s.title === "string")
}

/** 按 artifact.type 渲染结构化卡片；结构不符时降级为 JSON，避免整条消息崩溃 */
export function ArtifactView({
  artifact,
  onConfirmRequirement,
  readonly,
  selectedTier,
  onSelectTier,
}: {
  artifact: AgentArtifact
  /** 需求卡片「确认需求，出报价」 */
  onConfirmRequirement?: (requirement: Record<string, unknown>) => void
  readonly?: boolean
  /** 三档方案卡：选中的档位，以及可以点选时的回调 */
  selectedTier?: string
  onSelectTier?: (key: string) => void
}) {
  const { type, data } = artifact
  if (type === "requirement" && isRequirementCard(data))
    return <RequirementCard data={data} onConfirm={onConfirmRequirement} readOnly={readonly} />
  // core 的原始结构（packs/base.py）优先；也兼容已经是视图模型的数据
  if (type === "solution_tiers" && isCoreTiers(data))
    return <TierCards tiers={toTierCards(data)} selected={selectedTier} onSelect={onSelectTier} />
  if (type === "solution_tiers" && isTiers(data)) return <TierCards tiers={data} />
  if (type === "bom" && isCoreTier(data)) return <BomTable bom={toBomData(data)} />
  if (type === "bom" && isBom(data)) return <BomTable bom={data} />
  if (type === "quote" && isCoreQuote(data)) return <QuoteCard quote={data} />
  if (type === "sources" && isSources(data)) return <Sources sources={data} />
  return (
    <pre className="overflow-x-hidden rounded-lg border border-zinc-200 bg-zinc-50 p-3 font-mono text-[11px] break-all whitespace-pre-wrap text-zinc-600">
      {`[${type}]\n${JSON.stringify(data, null, 2)}`}
    </pre>
  )
}
