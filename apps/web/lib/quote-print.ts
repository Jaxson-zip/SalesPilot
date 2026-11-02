/** 报价单打印页的纯函数：合计、折扣（均来自后端返回的明细与总价，不重新计算价格规则） */
import type { QuoteDetail, QuoteLine } from "@/types/api"

import { canShareQuote } from "@/lib/share"

export const PRINT_COMPANY = "SalesPilot 演示公司"

/**
 * 能否打印正式报价单：和分享链接一样，审批通过后才行。
 * 打印出来的 PDF 就是发给客户的，草稿、待审批、已驳回的价格不能先流出去。
 */
export function canPrintQuote(status: string): boolean {
  return canShareQuote(status)
}

export interface PrintTotals {
  /** 明细小计之和（折前，分） */
  subtotal: number
  /** 折扣金额（分）= 折前 − 报价合计；没有折扣为 0 */
  discountAmount: number
  /** 报价合计（分，后端 total_price） */
  total: number
  /** 0–1；后端没返回时按金额反推 */
  discountRate: number
}

export function printTotals(q: Pick<QuoteDetail, "items" | "total_price" | "discount_rate">): PrintTotals {
  const subtotal = q.items.reduce((s, it) => s + it.subtotal_price, 0)
  const discountAmount = Math.max(0, subtotal - q.total_price)
  const discountRate = q.discount_rate ?? (subtotal > 0 ? discountAmount / subtotal : 0)
  return { subtotal, discountAmount, total: q.total_price, discountRate }
}

/** 打印页标题（浏览器「存为 PDF」默认文件名）：报价单-Q-2026-018-客户名 */
export function printDocTitle(q: Pick<QuoteDetail, "code" | "customer">): string {
  return ["报价单", q.code, q.customer?.name].filter(Boolean).join("-")
}

export const PLATFORM_NAMES: Record<string, string> = {
  mini_program: "微信小程序",
  app: "App",
  web: "网站 / H5",
  admin: "管理后台",
}

export interface PrintScope {
  platforms: string
  delivery: "团队" | "个人全栈"
  /** 需求清单里有、但这一档报价没有包含的功能（二期或经济版砍掉的） */
  excluded: string[]
}

/**
 * 软件外包报价单的「项目范围」：来自商机上确认过的需求清单。
 * 功能明细已在报价表里（明细名称以模块名开头），这里只补交付端、交付方式和「本期不含」，
 * 让客户看清哪些功能不在这次的价格里，避免签约后扯皮。
 */
export function printScope(
  req: {
    platforms?: string[]
    modules?: { name: string }[]
    team_size?: number | null
    excluded_platforms?: string[]
    excluded_modules?: string[]
  },
  items: Pick<QuoteLine, "name">[],
): PrintScope {
  const quoted = (name: string) => items.some((it) => it.name.startsWith(name))
  // core 按档位算好了「不含」就用它（经济版只做第一个端）；旧数据按明细比对模块
  const modules = req.excluded_modules ?? (req.modules ?? []).map((m) => m.name).filter((n) => !quoted(n))
  const name = (p: string) => PLATFORM_NAMES[p] ?? p
  return {
    platforms: (req.platforms ?? []).map(name).join("、"),
    delivery: req.team_size === 1 ? "个人全栈" : "团队",
    excluded: [...(req.excluded_platforms ?? []).map(name), ...modules],
  }
}
