import { describe, expect, it } from "vitest"

import { describeRules, formatBytes, formatRuleValue, specText } from "@/lib/pack-rules"

describe("describeRules", () => {
  it("已知键翻译成中文并格式化", () => {
    const rows = describeRules({
      margin: { floor_rate: 0.25 },
      expense: { entertainment_per_person: 15000 },
      attachment: { max_bytes: 10485760 },
    })
    expect(rows).toEqual([
      { key: "margin.floor_rate", label: "毛利底线（低于需主管审批）", value: "25%" },
      { key: "expense.entertainment_per_person", label: "客户招待标准（每人）", value: "¥150" },
      { key: "attachment.max_bytes", label: "单个票据大小上限", value: "10 MB" },
    ])
  })

  it("方案档位逐档展开，字段翻译", () => {
    const rows = describeRules({ pack: { tiers: { standard: { gpu: "L20", ha: false, tuning_days: 5 } } } })
    expect(rows).toEqual([
      { key: "pack.tiers.standard", label: "方案档位 · 标准版", value: "GPU L20 · 高可用 否 · 调优天数 5" },
    ])
  })

  it("未知键保留路径，数组用 / 连接", () => {
    const rows = describeRules({ foo: { bar: [1, 2] }, pack: { economy_discount_ladder: [0.08, 0] } })
    expect(rows).toEqual([
      { key: "foo.bar", label: "foo.bar", value: "1 / 2" },
      { key: "pack.economy_discount_ladder", label: "经济版折扣阶梯（逐级回退）", value: "8% / 0%" },
    ])
  })

  it("空规则返回空列表", () => {
    expect(describeRules({})).toEqual([])
  })
})

describe("格式化", () => {
  it("formatRuleValue", () => {
    expect(formatRuleValue(true)).toBe("是")
    expect(formatRuleValue(null)).toBe("—")
    expect(formatRuleValue(1.2, "times")).toBe("1.2 倍")
  })
  it("formatBytes", () => {
    expect(formatBytes(512)).toBe("512 B")
    expect(formatBytes(2048)).toBe("2 KB")
    expect(formatBytes(1572864)).toBe("1.5 MB")
    expect(formatBytes(-1)).toBe("—")
  })
  it("specText", () => {
    expect(specText(null)).toBe("")
    expect(specText("48GB")).toBe("48GB")
    expect(specText({ vram_gb: 48, nvlink: false })).toBe("vram_gb: 48，nvlink: 否")
  })
})

describe("describeRules · 软件外包", () => {
  it("档位枚举和比例转中文，模块库显示人天，缺省键不出行", () => {
    const rows = describeRules({
      pack: {
        tiers: { economy: { scope: "must", platforms: "first", handover: false, ratios: { qa: 0.15 } } },
        modules: { booking: { name: "在线预约排期", days: [4, 7, 12] } },
        tensor_parallel_sizes: undefined,
      },
    })
    expect(rows.map((r) => r.label)).toEqual(["方案档位 · 经济版", "模块库 · 在线预约排期"])
    expect(rows[0].value).toBe(
      "功能范围 只做首期必须的功能 · 交付端 只做第一个客户端 · 源码交付与培训 否 · 比例调整 测试 15%",
    )
    expect(rows[1].value).toBe("简单 4 / 中等 7 / 复杂 12 人天")
  })
})
