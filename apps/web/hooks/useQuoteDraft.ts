"use client"

import { useEffect, useState } from "react"

import type { CoreSolutionTier } from "@/lib/artifacts"
import type { QtyEdits } from "@/lib/bom-adjust"
import { restoreDraft, serializeDraft, tiersFingerprint } from "@/lib/quote-draft"
import { readStorage, writeStorage } from "@/lib/storage"

export type DraftNotice = "restored" | "stale" | null

/**
 * 待确认方案的档位和物料调整：key 为空（不在待确认状态）时只在内存里；
 * 有 key 时挂载后从 localStorage 恢复，之后每次调整写回，clear() 在确认 / 取消时删掉。
 */
export function useQuoteDraft(key: string | null, tiers: CoreSolutionTier[]) {
  const fp = tiersFingerprint(tiers)
  const [picked, setPicked] = useState<string | null>(null)
  const [editsByTier, setEditsByTier] = useState<Record<string, QtyEdits>>({})
  const [notice, setNotice] = useState<DraftNotice>(null)
  // 读完存储之后才写回，避免挂载时用空状态把存着的调整覆盖掉
  const [ready, setReady] = useState<string | null>(null)

  useEffect(() => {
    if (!key || !fp) return
    const r = restoreDraft(readStorage(key), fp, tiers)
    if (r.status === "restored") {
      setPicked(r.draft.picked)
      setEditsByTier(r.draft.edits)
    }
    if (r.status === "stale") writeStorage(key, null)
    setNotice(r.status === "none" ? null : r.status)
    setReady(key)
    // tiers 由 fp 代表；只在会话或方案变了时重新读
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, fp])

  useEffect(() => {
    if (!key || ready !== key) return
    writeStorage(key, serializeDraft(fp, { picked, edits: editsByTier }))
  }, [key, ready, fp, picked, editsByTier])

  const clear = () => {
    if (key) writeStorage(key, null)
    setReady(null)
    setNotice(null)
  }
  return { picked, setPicked, editsByTier, setEditsByTier, notice, clear }
}
