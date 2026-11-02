import { describe, expect, it } from "vitest"

import { printDocTitle, printScope, printTotals } from "@/lib/quote-print"
import { fenToRmbUpper } from "@/lib/rmb"

describe("金额大写", () => {
  it("整数元加「整」", () => {
    expect(fenToRmbUpper(0)).toBe("零元整")
    expect(fenToRmbUpper(100)).toBe("壹元整")
    expect(fenToRmbUpper(37200000)).toBe("叁拾柒万贰仟元整")
    expect(fenToRmbUpper(10000000000)).toBe("壹亿元整")
  })
  it("中间的 0 读一个「零」", () => {
    expect(fenToRmbUpper(100500)).toBe("壹仟零伍元整")
    expect(fenToRmbUpper(1000500)).toBe("壹万零伍元整")
    expect(fenToRmbUpper(10001000000)).toBe("壹亿零壹万元整")
    expect(fenToRmbUpper(1050000)).toBe("壹万零伍佰元整")
  })
  it("角分", () => {
    expect(fenToRmbUpper(1234567)).toBe("壹万贰仟叁佰肆拾伍元陆角柒分")
    expect(fenToRmbUpper(105)).toBe("壹元零伍分")
    expect(fenToRmbUpper(150)).toBe("壹元伍角")
    expect(fenToRmbUpper(5)).toBe("伍分")
  })
  it("非法输入返回空串", () => {
    expect(fenToRmbUpper(-1)).toBe("")
    expect(fenToRmbUpper(1.5)).toBe("")
  })
})

describe("报价单打印", () => {
  const line = {
    sku: "a",
    name: "A",
    unit: "台",
    qty: 1,
    unit_cost: 1,
    unit_price: 100000,
    category: "hw",
    subtotal_cost: 1,
  }
  it("折扣 = 折前小计 − 报价合计", () => {
    const t = printTotals({
      items: [
        { ...line, subtotal_price: 100000 },
        { ...line, sku: "b", subtotal_price: 50000 },
      ],
      total_price: 138000,
      discount_rate: 0.08,
    })
    expect(t).toEqual({ subtotal: 150000, discountAmount: 12000, total: 138000, discountRate: 0.08 })
  })
  it("后端没给 discount_rate 时按金额反推；没有折扣为 0", () => {
    expect(printTotals({ items: [{ ...line, subtotal_price: 100000 }], total_price: 90000 }).discountRate).toBe(0.1)
    expect(printTotals({ items: [{ ...line, subtotal_price: 100000 }], total_price: 100000 }).discountAmount).toBe(0)
  })
  it("文档标题（存为 PDF 的文件名）", () => {
    expect(printDocTitle({ code: "Q-2026-018", customer: { id: "c", name: "明理律所" } })).toBe(
      "报价单-Q-2026-018-明理律所",
    )
    expect(printDocTitle({ code: "Q-1", customer: null })).toBe("报价单-Q-1")
  })
})

describe("报价单项目范围", () => {
  it("列出交付端、交付方式和这一档没有包含的功能", () => {
    const req = {
      platforms: ["mini_program", "admin"],
      team_size: 1,
      modules: [{ name: "在线预约" }, { name: "会员积分" }, { name: "数据报表" }],
    }
    const items = [{ name: "在线预约（复杂）" }, { name: "数据报表（中等）" }, { name: "UI 设计" }]
    expect(printScope(req, items)).toEqual({
      platforms: "微信小程序、管理后台",
      delivery: "个人全栈",
      excluded: ["会员积分"],
    })
    expect(printScope({}, []).delivery).toBe("团队")
  })

  it("core 按档位算好的「不含」优先：经济版没报价的 App 也列进去", () => {
    const scope = {
      platforms: ["mini_program"],
      modules: [{ name: "在线预约" }],
      excluded_platforms: ["app"],
      excluded_modules: ["会员积分"],
    }
    expect(printScope(scope, [{ name: "在线预约（简单）" }]).excluded).toEqual(["App", "会员积分"])
  })
})
