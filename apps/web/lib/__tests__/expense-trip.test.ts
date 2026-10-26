import { describe, expect, it } from "vitest"

import {
  applyTemplate,
  EMPTY_TRIP,
  hotelSummary,
  nightsBetween,
  toDetails,
  tripErrors,
  tripText,
} from "@/lib/expense-trip"
import type { ExpenseTemplate } from "@/types/api"

const hotel = { ...EMPTY_TRIP, city: "北京", check_in: "2026-10-01", check_out: "2026-10-03" }

describe("nightsBetween", () => {
  it("按自然日算晚数；跨月也正确；离店不晚于入住为 0", () => {
    expect(nightsBetween("2026-10-01", "2026-10-03")).toBe(2)
    expect(nightsBetween("2026-10-31", "2026-11-01")).toBe(1)
    expect(nightsBetween("2026-10-03", "2026-10-03")).toBe(0)
    expect(nightsBetween("", "2026-10-03")).toBe(0)
  })
})

describe("tripErrors", () => {
  it("住宿必填城市和日期，离店要晚于入住，最多 60 晚", () => {
    expect(tripErrors("hotel", EMPTY_TRIP)).toEqual({
      city: "请填写住宿城市",
      check_in: "请选择入住日期",
      check_out: "请选择离店日期",
    })
    expect(tripErrors("hotel", { ...hotel, check_out: "2026-10-01" }).check_out).toBe("离店日期要晚于入住日期")
    expect(tripErrors("hotel", { ...hotel, check_out: "2027-01-01" }).check_out).toContain("最多 60 晚")
    expect(tripErrors("hotel", hotel)).toEqual({})
  })

  it("交通和其他类型不校验行程", () => {
    expect(tripErrors("transport", EMPTY_TRIP)).toEqual({})
    expect(tripErrors("entertainment", EMPTY_TRIP)).toEqual({})
  })
})

describe("toDetails", () => {
  it("住宿传城市和日期；交通只传填了的字段；招待不传", () => {
    expect(toDetails("hotel", hotel)).toEqual({ city: "北京", check_in: "2026-10-01", check_out: "2026-10-03" })
    expect(toDetails("transport", { ...EMPTY_TRIP, from_city: " 深圳 ", transport_mode: "train" })).toEqual({
      from_city: "深圳",
      transport_mode: "train",
    })
    expect(toDetails("transport", EMPTY_TRIP)).toBeUndefined()
    expect(toDetails("entertainment", hotel)).toBeUndefined()
  })
})

describe("hotelSummary / tripText", () => {
  it("显示晚数和每晚金额", () => {
    expect(hotelSummary("1200", hotel)).toBe("共 2 晚，每晚 ¥600")
    expect(hotelSummary("", hotel)).toBe("共 2 晚")
    expect(hotelSummary("1200", EMPTY_TRIP)).toBeNull()
  })

  it("详情页行程摘要", () => {
    expect(tripText({ city: "北京", check_in: "2026-10-01", check_out: "2026-10-03" })).toBe(
      "北京 · 2 晚（2026-10-01 至 2026-10-03）",
    )
    expect(tripText({ from_city: "深圳", to_city: "北京", transport_mode: "train" })).toBe("深圳 → 北京 · 高铁 / 火车")
    expect(tripText(null)).toBeNull()
  })
})

describe("applyTemplate", () => {
  const templates: ExpenseTemplate[] = [
    { id: "a", label: "客户餐叙", type: "entertainment", transport_mode: null, reason: "方案沟通餐叙：", example: "" },
    { id: "b", label: "出差高铁", type: "transport", transport_mode: "train", reason: "出差拜访客户：", example: "" },
  ]
  const base = { type: "entertainment" as const, reason: "", trip: EMPTY_TRIP }

  it("带出类型、交通方式和事由开头", () => {
    const v = applyTemplate(base, templates[1], templates)
    expect(v.type).toBe("transport")
    expect(v.reason).toBe("出差拜访客户：")
    expect(v.trip.transport_mode).toBe("train")
  })

  it("切换模板时替换未修改的事由开头，但不覆盖用户写过的内容", () => {
    const switched = applyTemplate({ ...base, reason: "方案沟通餐叙：" }, templates[1], templates)
    expect(switched.reason).toBe("出差拜访客户：")
    const kept = applyTemplate({ ...base, reason: "方案沟通餐叙：和王律师谈预算" }, templates[1], templates)
    expect(kept.reason).toBe("方案沟通餐叙：和王律师谈预算")
  })
})
