/** 记录页链接：点名字、编号直接打开那一条（和后端通知里的 subject_link 一致） */
import { contractHref } from "@/lib/contract"

export function customerHref(id: string): string {
  return `/customers/${encodeURIComponent(id)}`
}

/** 商机没有单独页面：看板打开侧栏 */
export function opportunityHref(id: string): string {
  return `/pipeline?opp=${encodeURIComponent(id)}`
}

export function quoteHref(id: string): string {
  return `/quotes/${encodeURIComponent(id)}`
}

/** 报销在列表页打开这张单子 */
export function expenseHref(id: string): string {
  return `/expenses?id=${encodeURIComponent(id)}`
}

/** 报销列表只看这个商机的费用 */
export function opportunityExpensesHref(opportunityId: string): string {
  return `/expenses?opp=${encodeURIComponent(opportunityId)}`
}

/** 动态、通知等按对象类型跳转；不认识的类型返回 null（不放链接） */
export function subjectHref(type: string, id: string): string | null {
  switch (type) {
    case "customer":
      return customerHref(id)
    case "opportunity":
      return opportunityHref(id)
    case "quote":
      return quoteHref(id)
    case "contract":
      return contractHref(id)
    case "expense":
      return expenseHref(id)
    default:
      return null
  }
}

/** 新建报价：从客户进来带上客户（客户详情「报价单」页签的入口） */
export function newQuoteForCustomerHref(customerId: string): string {
  return `/quotes/new?customer=${encodeURIComponent(customerId)}`
}
