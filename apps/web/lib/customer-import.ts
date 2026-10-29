/** 客户批量导入（契约 §26）：模板、预览结果的统计和文案 */

/** POST /api/customers/import(/preview) 的一行 */
export interface ImportRow {
  /** 文件里的行号（表头是第 1 行） */
  line: number
  name: string
  /** 导入后的负责人；null 表示本团队公海 */
  owner_name: string | null
  status: "ok" | "duplicate" | "error"
  message: string | null
  warnings: string[]
}

export interface ImportResult {
  total: number
  /** 预览：可以导入的行数；导入：实际新建的客户数 */
  ok: number
  skipped: number
  created: boolean
  columns: string[]
  ignored_columns: string[]
  rows: ImportRow[]
}

const HEADER = [
  "客户名称*",
  "行业",
  "等级",
  "规模",
  "地址",
  "网站",
  "年度预算（元）",
  "标签",
  "联系人",
  "职位",
  "电话",
  "联系人角色",
]
const SAMPLE = [
  "深圳示例科技有限公司",
  "制造业",
  "B",
  "100-500人",
  "深圳市南山区",
  "",
  "5万",
  "重点、华南",
  "王总",
  "总经理",
  "13800000000",
  "决策人",
]

/** 模板 CSV（带 BOM，Excel 直接打开不乱码）；主管多一列「负责人」 */
export function importTemplate(manager: boolean): string {
  const header = manager ? [...HEADER, "负责人"] : HEADER
  const sample = manager ? [...SAMPLE, "公海"] : SAMPLE
  return "\uFEFF" + [header, sample].map((r) => r.join(",")).join("\r\n") + "\r\n"
}

export const ACCEPT = ".csv,.xlsx"
export const MAX_BYTES = 2 * 1024 * 1024

/** 选文件时先在浏览器里拦掉明显不对的，省一次上传 */
export function fileProblem(file: { name: string; size: number }): string | null {
  if (!/\.(csv|xlsx)$/i.test(file.name)) return "只支持 .csv 和 .xlsx 文件"
  if (file.size > MAX_BYTES) return "文件超过 2MB，请拆成几个文件导入"
  return null
}

/** 预览汇总：「共 12 行：可导入 9 行，跳过 3 行（已存在 2、有错误 1）」 */
export function previewSummary(r: ImportResult): string {
  const dup = r.rows.filter((x) => x.status === "duplicate").length
  const err = r.rows.filter((x) => x.status === "error").length
  const parts = [dup ? `重复 ${dup}` : "", err ? `有错误 ${err}` : ""].filter(Boolean)
  const skipped = r.skipped ? `，跳过 ${r.skipped} 行（${parts.join("、")}）` : ""
  return `共 ${r.total} 行：可导入 ${r.ok} 行${skipped}`
}

/** 预览表只列有问题或有提示的行，正常行太多时不刷屏 */
export function rowsToShow(r: ImportResult): ImportRow[] {
  return r.rows.filter((x) => x.status !== "ok" || x.warnings.length > 0)
}
