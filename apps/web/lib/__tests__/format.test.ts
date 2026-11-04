import { describe, expect, it } from "vitest"

import {
  addDays,
  displayHost,
  followupOccurredAt,
  formatFen,
  formatPercent,
  formatRelative,
  localDate,
} from "@/lib/format"

describe("formatFen（后端传分，前端格式化）", () => {
  it("整元不带小数，有分时保留两位", () => {
    expect(formatFen(37200000)).toBe("¥372,000")
    expect(formatFen(123450)).toBe("¥1,234.50")
    expect(formatFen(0)).toBe("¥0")
  })

  it("负数（冲正记录）写成 -¥100", () => {
    expect(formatFen(-10000)).toBe("-¥100")
    expect(formatFen(-123450)).toBe("-¥1,234.50")
  })

  it("空值显示占位符", () => {
    expect(formatFen(null)).toBe("—")
    expect(formatFen(undefined)).toBe("—")
    expect(formatFen(Number.NaN)).toBe("—")
  })
})

describe("formatPercent", () => {
  it("0–1 转百分比，默认一位小数", () => {
    expect(formatPercent(0.2944)).toBe("29.4%")
    expect(formatPercent(0.25, 0)).toBe("25%")
  })
})

describe("formatRelative", () => {
  const now = new Date(2026, 9, 25, 15, 0, 0)
  it("按时间远近给出不同写法", () => {
    expect(formatRelative(new Date(2026, 9, 25, 14, 59, 30).toISOString(), now)).toBe("刚刚")
    expect(formatRelative(new Date(2026, 9, 25, 14, 30).toISOString(), now)).toBe("30 分钟前")
    expect(formatRelative(new Date(2026, 9, 25, 10, 0).toISOString(), now)).toBe("5 小时前")
    expect(formatRelative(new Date(2026, 9, 24, 9, 0).toISOString(), now)).toBe("昨天")
    expect(formatRelative(new Date(2026, 8, 3).toISOString(), now)).toBe("09-03")
    expect(formatRelative(new Date(2025, 0, 2).toISOString(), now)).toBe("2025-01-02")
    expect(formatRelative(null, now)).toBe("—")
    expect(formatRelative("not-a-date", now)).toBe("—")
  })
})

describe("displayHost", () => {
  it("去掉协议和末尾斜杠", () => {
    expect(displayHost("https://mingli-law.cn/")).toBe("mingli-law.cn")
    expect(displayHost(null)).toBe("")
  })
})

describe("localDate（业务日期按北京时间）", () => {
  it("回归：曾用 toISOString（UTC），东八区凌晨差一天", () => {
    expect(localDate(new Date("2026-10-26T00:30:00+08:00"))).toBe("2026-10-26")
    expect(localDate(new Date("2026-01-05T23:59:00+08:00"))).toBe("2026-01-05")
  })
  it("回归：浏览器在太平洋时间时，取的是浏览器日期，和后端差一天", () => {
    expect(localDate(new Date("2026-11-03T08:35:00-08:00"))).toBe("2026-11-04")
    expect(localDate(new Date("2026-11-03T15:59:00Z"))).toBe("2026-11-03")
    expect(localDate(new Date("2026-11-03T16:00:00Z"))).toBe("2026-11-04")
  })
  it("日期加减跨月跨年", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01")
    expect(addDays("2027-01-01", -1)).toBe("2026-12-31")
    expect(addDays("2026-11-04", -31)).toBe("2026-10-04")
  })
})

// 回归：跟进日期拼成「当天 00:00」不带时区，刚保存的跟进显示「15 小时前」
describe("followupOccurredAt", () => {
  const now = new Date("2026-11-03T15:30:00+08:00")
  it("今天不传，由后端记为保存时间", () => {
    expect(followupOccurredAt("2026-11-03", now)).toBeUndefined()
    expect(followupOccurredAt("", now)).toBeUndefined()
  })
  it("补记往日：那天北京时间的此刻，带时区", () => {
    expect(followupOccurredAt("2026-11-01", now)).toBe(new Date("2026-11-01T15:30:00+08:00").toISOString())
  })
})
