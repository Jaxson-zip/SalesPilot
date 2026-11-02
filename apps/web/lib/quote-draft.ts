/**
 * 「生成报价单」确认前的方案调整（选中的档位 + 每档物料数量）存在本机，
 * 切到别的页面或刷新后回到同一会话能恢复，避免按默认档位误确认。
 * 按「用户 + 会话」存；同时记下这次三档方案的指纹，方案重新生成过就不恢复（并提示重新核对）。
 */
import type { CoreSolutionTier } from "@/lib/artifacts"
import { MAX_ADJUST_QTY, type QtyEdits } from "@/lib/bom-adjust"

export interface QuoteDraft {
  picked: string | null
  edits: Record<string, QtyEdits>
}

export type DraftRestore = { status: "none" } | { status: "stale" } | { status: "restored"; draft: QuoteDraft }

export function quoteDraftKey(userId: string, threadId: string): string {
  return `sp.quote-draft.${userId}.${threadId}`
}

/** 三档方案的指纹：档位、总价和每行物料数量都一样才算同一份方案 */
export function tiersFingerprint(tiers: CoreSolutionTier[]): string {
  return tiers.map((t) => `${t.tier}:${t.total_price}:${t.items.map((i) => `${i.sku}x${i.qty}`).join(",")}`).join("|")
}

export function isEmptyDraft(d: QuoteDraft): boolean {
  return !d.picked && Object.values(d.edits).every((e) => Object.keys(e).length === 0)
}

export function serializeDraft(fingerprint: string, d: QuoteDraft): string | null {
  return isEmptyDraft(d) ? null : JSON.stringify({ fp: fingerprint, picked: d.picked, edits: d.edits })
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null

/** 只保留当前方案里存在的档位和物料、合法的数量 */
function cleanEdits(raw: unknown, tiers: CoreSolutionTier[]): Record<string, QtyEdits> {
  const out: Record<string, QtyEdits> = {}
  if (!isObj(raw)) return out
  for (const t of tiers) {
    const e = raw[t.tier]
    if (!isObj(e)) continue
    const skus = new Set(t.items.map((i) => i.sku))
    const kept: QtyEdits = {}
    for (const [sku, q] of Object.entries(e)) {
      if (skus.has(sku) && Number.isInteger(q) && (q as number) >= 0 && (q as number) <= MAX_ADJUST_QTY)
        kept[sku] = q as number
    }
    if (Object.keys(kept).length) out[t.tier] = kept
  }
  return out
}

export function restoreDraft(raw: string | null, fingerprint: string, tiers: CoreSolutionTier[]): DraftRestore {
  if (!raw) return { status: "none" }
  let data: unknown
  try {
    data = JSON.parse(raw)
  } catch {
    return { status: "stale" }
  }
  if (!isObj(data) || data.fp !== fingerprint) return { status: "stale" }
  const picked = typeof data.picked === "string" && tiers.some((t) => t.tier === data.picked) ? data.picked : null
  const draft = { picked, edits: cleanEdits(data.edits, tiers) }
  return isEmptyDraft(draft) ? { status: "none" } : { status: "restored", draft }
}
