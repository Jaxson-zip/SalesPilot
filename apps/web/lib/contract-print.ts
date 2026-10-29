/** 合同要素确认单（合同打印页）的纯函数：标题、回款计划比例与核对 */
import { PLATFORM_NAMES } from "@/lib/quote-print"
import type { ContractItem, PaymentPlanItem } from "@/types/api"

/** 浏览器「存为 PDF」默认文件名：合同要素确认单-C-2026-001-客户名 */
export function contractDocTitle(c: Pick<ContractItem, "code" | "customer">): string {
  return ["合同要素确认单", c.code, c.customer?.name].filter(Boolean).join("-")
}

/** 某期占合同金额的比例，取整到 1%：「30%」 */
export function planRatio(amount: number, total: number): string {
  return total > 0 ? `${Math.round((amount / total) * 100)}%` : "—"
}

/** 回款计划各期之和与合同金额不一致时给出差额（分），一致为 0 */
export function planGap(items: Pick<PaymentPlanItem, "amount">[], total: number): number {
  return total - items.reduce((s, it) => s + it.amount, 0)
}

/** 合同附件里的需求范围（没有 PRD 时按已确认的需求清单列出）：交付端、各模块及首期 / 二期 */
export function sowScope(req: { platforms?: string[]; modules?: { name: string; must?: boolean }[] }): {
  platforms: string
  modules: { name: string; phase: string }[]
} {
  return {
    platforms: (req.platforms ?? []).map((p) => PLATFORM_NAMES[p] ?? p).join("、"),
    modules: (req.modules ?? []).map((m) => ({ name: m.name, phase: m.must === false ? "二期" : "首期" })),
  }
}

/** 附到合同里的 PRD：去掉「AI 草案 / 模板版」提示行（附进合同即视为双方确认的版本） */
export function prdForPrint(markdown: string): string {
  return markdown
    .split("\n")
    .filter((line) => !/^>\s*(AI 生成的草案|按需求清单生成的模板版)/.test(line))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
}
