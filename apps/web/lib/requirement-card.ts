/**
 * 需求卡片（artifact type = "requirement"，软件外包）：AI 拆出的交付端和功能模块，销售核对后确认再出正式报价。
 * 这里只做类型守卫和纯函数编辑；价格区间由 core 的配置器算好，前端不计算价格。
 */

export type Complexity = "simple" | "medium" | "complex"

export interface ReqModule {
  key: string
  name: string
  complexity: Complexity
  must: boolean
  source: "mentioned" | "inferred"
}

export interface Requirement {
  project?: string | null
  platforms: string[]
  modules: ReqModule[]
  deadline_weeks?: number | null
  budget?: number | null
  team_size?: number | null
  /** 客户没有 SOP / 流程文档：报价含业务调研与流程梳理 */
  no_sop?: boolean | null
  /** 上线后每月识别的图片张数（有图片识别模块时用来估月费；空 = 按默认月量） */
  ocr_monthly_pages?: number | null
  questions?: string[]
  [key: string]: unknown
}

export interface RequirementCardData {
  opportunity_id?: string | null
  requirement: Requirement
  /** 分 */
  price_low: number
  price_high: number
  inferred: number
  questions: string[]
  /** 配置器给销售的提醒：额外工作量、报价外的费用、建议先做验证等 */
  notes?: string[]
  /** 历史记录：已确认，requirement 是确认时的版本 */
  confirmed?: boolean
}

export const PLATFORMS: [string, string][] = [
  ["mini_program", "微信小程序"],
  ["app", "App"],
  ["web", "网站 / H5"],
  ["admin", "管理后台"],
]

export const COMPLEXITIES: [Complexity, string][] = [
  ["simple", "简单"],
  ["medium", "中等"],
  ["complex", "复杂"],
]

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null

export function isRequirementCard(v: unknown): v is RequirementCardData {
  if (!isObj(v) || !isObj(v.requirement)) return false
  const r = v.requirement
  return (
    typeof v.price_low === "number" &&
    typeof v.price_high === "number" &&
    Array.isArray(r.platforms) &&
    Array.isArray(r.modules) &&
    r.modules.every((m) => isObj(m) && typeof m.name === "string")
  )
}

/** 单选 / 多选切换交付端（至少保留一个由确认按钮校验） */
export function togglePlatform(r: Requirement, p: string): Requirement {
  const has = r.platforms.includes(p)
  return { ...r, platforms: has ? r.platforms.filter((x) => x !== p) : [...r.platforms, p] }
}

export function updateModule(r: Requirement, index: number, patch: Partial<ReqModule>): Requirement {
  return { ...r, modules: r.modules.map((m, i) => (i === index ? { ...m, ...patch } : m)) }
}

export function removeModule(r: Requirement, index: number): Requirement {
  return { ...r, modules: r.modules.filter((_, i) => i !== index) }
}

/** 手动补充的功能：不在模块库里，按自定义模块（中等）估算；销售加的算「客户提到」 */
export function addModule(r: Requirement, name: string): Requirement {
  const n = name.trim()
  if (!n || r.modules.some((m) => m.name === n)) return r
  return {
    ...r,
    modules: [...r.modules, { key: "custom", name: n, complexity: "medium", must: true, source: "mentioned" }],
  }
}

/** 确认提交：销售核对过的模块都算客户确认的，不再带 AI 生成的问题 */
export function confirmedRequirement(r: Requirement): Record<string, unknown> {
  return { ...r, questions: [], modules: r.modules.map((m) => ({ ...m, source: "mentioned" })) }
}

/** 有图片 / 单据识别模块时才需要填每月识别量 */
export function hasOcr(r: Requirement): boolean {
  return r.modules.some((m) => m.key === "ocr")
}

/** 每月识别量输入框：空或非法 → null（按默认月量估），否则取非负整数 */
export function parsePages(text: string): number | null {
  const n = Number(text.replace(/[,，\s]/g, ""))
  return text.trim() && Number.isFinite(n) && n >= 0 ? Math.round(n) : null
}

export function canConfirm(r: Requirement): boolean {
  return r.platforms.length > 0 && r.modules.length > 0
}
