import { describe, expect, it } from "vitest"

import { formatSetting, parseInputText, toInputText, validateStages } from "@/lib/settings"

const field = (kind: Parameters<typeof toInputText>[0], min: number | null = null, max: number | null = null) => ({
  kind,
  min,
  max,
  label: "测试",
})

describe("配置项输入转换", () => {
  it("比例：输入 25 存 0.25，范围按存储单位", () => {
    expect(toInputText("percent", 0.07)).toBe("7")
    expect(parseInputText(field("percent", 0, 0.9), "7")).toEqual({ ok: true, value: 0.07 })
    expect(parseInputText(field("percent", 0, 0.9), "95").ok).toBe(false)
  })

  it("金额：输入元、存分", () => {
    expect(toInputText("money", 15000)).toBe("150")
    expect(parseInputText(field("money", 0), "150.5")).toEqual({ ok: true, value: 15050 })
    expect(formatSetting("money", 35000, "元/晚")).toBe("¥350/晚")
  })

  it("整数与 MB", () => {
    expect(parseInputText(field("int", 1, 365), "2.5")).toEqual({ ok: false, error: "「测试」请填写整数" })
    expect(parseInputText(field("megabytes", 1, 50), "20")).toEqual({ ok: true, value: 20 * 1024 * 1024 })
    expect(parseInputText(field("megabytes", 1, 50), "60").ok).toBe(false)
  })

  it("城市与比例列表", () => {
    expect(parseInputText(field("cities"), "北京、上海, 深圳 北京")).toEqual({
      ok: true,
      value: ["北京", "上海", "深圳"],
    })
    expect(parseInputText(field("percent_list", 0, 0.5), "8、4、0")).toEqual({ ok: true, value: [0.08, 0.04, 0] })
    expect(formatSetting("percent_list", [0.08, 0.04, 0])).toBe("8% → 4% → 0%")
  })

  it("回款计划合计必须 100%", () => {
    const ok = [
      { name: "预付款", ratio: 0.3, due_days: 0 },
      { name: "到货验收款", ratio: 0.6, due_days: 60 },
      { name: "质保金", ratio: 0.1, due_days: 425 },
    ]
    expect(validateStages(ok)).toBeNull()
    expect(validateStages([{ name: "预付款", ratio: 0.5, due_days: 0 }])).toContain("必须是 100%")
    expect(formatSetting("stages", ok)).toBe("预付款 30%（签订当天），到货验收款 60%（60 天），质保金 10%（425 天）")
  })
})
