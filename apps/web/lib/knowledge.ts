/** 行业包知识库的统计（纯函数）：顶部汇总和每份文档的状态用同一个口径 */

interface KnowledgeDocLike {
  indexed?: boolean
  chunks?: number | null
}

export interface KnowledgeSummary {
  /** 文档总数（含配置数据） */
  total: number
  /** 会进入知识库的格式（md / pdf / xlsx 等） */
  indexable: number
  /** 已切块入库、AI 能检索到的 */
  ingested: number
}

export function knowledgeSummary(docs: KnowledgeDocLike[]): KnowledgeSummary {
  const indexable = docs.filter((d) => d.indexed !== false)
  return {
    total: docs.length,
    indexable: indexable.length,
    ingested: indexable.filter((d) => (d.chunks ?? 0) > 0).length,
  }
}

/** 顶部一行：「4 份文档 · 3 份可检索，已入库 1 份」；统计不到切块数时不说已入库多少 */
export function knowledgeSummaryText(s: KnowledgeSummary, chunksKnown: boolean): string {
  const head = `${s.total} 份文档 · ${s.indexable} 份可检索`
  return chunksKnown ? `${head}，已入库 ${s.ingested} 份` : head
}

/** 有可检索的文档没入库时的说明：AI 查不到它们 */
export function knowledgeMissingHint(s: KnowledgeSummary, chunksKnown: boolean): string | null {
  if (!chunksKnown || s.ingested >= s.indexable) return null
  return `${s.indexable - s.ingested} 份文档还没入库，AI 暂时检索不到：通常是还没配置 Embedding 模型，配好后请管理员重新入库（重新上传或运行入库命令）。`
}
