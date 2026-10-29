/** PRD 规格书（GET/POST /api/opportunities/{id}/requirement/prd）：类型与导出用的纯函数 */

export interface Prd {
  markdown: string
  /** ai：模型扩写；template：模型不可用时按需求清单拼的模板版 */
  source: "ai" | "template"
  generated_at: string
  generated_by: string
  requirement_at: string
  /** 生成时需求清单是否已和客户确认 */
  confirmed: boolean
  /** 需求清单之后又改过，建议重新生成 */
  stale: boolean
}

export function isPrd(v: unknown): v is Prd {
  return typeof v === "object" && v !== null && typeof (v as Prd).markdown === "string"
}

/** 下载文件名：「商机名-PRD规格书.md」，去掉文件名里不允许的字符 */
export function prdFileName(title: string): string {
  const base = title.replace(/[\/:*?"<>|\s]+/g, "-").replace(/^-+|-+$/g, "")
  return `${base || "项目"}-PRD规格书.md`
}
