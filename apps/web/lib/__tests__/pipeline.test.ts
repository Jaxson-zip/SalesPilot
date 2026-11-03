import { describe, expect, it } from "vitest"

import {
  applyStageChange,
  checkStageMove,
  funnelWidths,
  groupByStage,
  isStage,
  KANBAN_STAGES,
  LIST_STAGES,
  normalizeFunnel,
  stageBarState,
  sumAmount,
} from "@/lib/pipeline"
import type { OpportunityItem, Paged } from "@/types/api"

function opp(id: string, stage: OpportunityItem["stage"], amount = 100): OpportunityItem {
  return {
    id,
    name: `商机${id}`,
    customer: { id: "c1", name: "客户" },
    stage,
    amount,
    win_rate: 10,
    expected_close_date: null,
    product_line: null,
    owner: { id: "u1", name: "张晨" },
    updated_at: "2026-10-01T00:00:00Z",
  }
}

describe("groupByStage / sumAmount", () => {
  it("按阶段分组并汇总金额", () => {
    const g = groupByStage([opp("1", "lead", 100), opp("2", "lead", 50), opp("3", "won")])
    expect(g.lead.map((o) => o.id)).toEqual(["1", "2"])
    expect(g.won).toHaveLength(1)
    expect(g.lost).toHaveLength(0)
    expect(sumAmount(g.lead)).toBe(150)
  })

  it("输单商机有地方显示（回归：筛选输单显示 4 条，看板各列都是空的）", () => {
    const g = groupByStage([opp("1", "lost"), opp("2", "lead")])
    expect(g.lost.map((o) => o.id)).toEqual(["1"])
    // 看板五列不含输单（输单在看板下面单独列出）；手机端标签要包含输单
    expect(KANBAN_STAGES).not.toContain("lost")
    expect(LIST_STAGES).toEqual([...KANBAN_STAGES, "lost"])
  })
})

describe("checkStageMove", () => {
  it("终态不能再切换", () => {
    expect(checkStageMove("won", "lead").ok).toBe(false)
    expect(checkStageMove("lost", "proposal").ok).toBe(false)
  })
  it("同阶段不发请求", () => {
    expect(checkStageMove("lead", "lead").ok).toBe(false)
  })
  it("进行中的阶段可以前进、后退或输单", () => {
    expect(checkStageMove("proposal", "qualified").ok).toBe(true)
    expect(checkStageMove("negotiation", "lost").ok).toBe(true)
  })
})

describe("applyStageChange（乐观更新）", () => {
  const page: Paged<OpportunityItem> = { items: [opp("1", "lead"), opp("2", "qualified")], total: 2 }
  const now = new Date("2026-10-25T08:00:00Z")

  it("只改目标记录，返回新对象", () => {
    const next = applyStageChange(page, "1", "proposal", now)
    expect(next).not.toBe(page)
    expect(next?.items[0].stage).toBe("proposal")
    expect(next?.items[0].updated_at).toBe(now.toISOString())
    expect(next?.items[1]).toBe(page.items[1])
    expect(page.items[0].stage).toBe("lead")
  })

  it("找不到记录或缓存为空时原样返回", () => {
    expect(applyStageChange(page, "x", "won", now)).toBe(page)
    expect(applyStageChange(undefined, "1", "won", now)).toBeUndefined()
  })
})

describe("漏斗", () => {
  it("宽度按最大值取百分比，非零最少 4%", () => {
    expect(
      funnelWidths([
        { stage: "lead", count: 50, amount: 0 },
        { stage: "qualified", count: 25, amount: 0 },
        { stage: "proposal", count: 0, amount: 0 },
        { stage: "won", count: 1, amount: 0 },
      ]),
    ).toEqual([100, 50, 0, 4])
    expect(funnelWidths([{ stage: "lead", count: 0, amount: 0 }])).toEqual([0])
  })

  it("按推进顺序补齐并去掉输单", () => {
    const f = normalizeFunnel([
      { stage: "won", count: 2, amount: 9 },
      { stage: "lost", count: 1, amount: 1 },
    ])
    expect(f.map((s) => s.stage)).toEqual(["lead", "qualified", "proposal", "negotiation", "won"])
    expect(f[4].count).toBe(2)
    expect(f[0].count).toBe(0)
  })
})

describe("stageBarState / isStage", () => {
  it("阶段条状态", () => {
    expect(stageBarState("proposal", "lead")).toBe("done")
    expect(stageBarState("proposal", "proposal")).toBe("current")
    expect(stageBarState("proposal", "won")).toBe("todo")
    expect(stageBarState("lost", "lead")).toBe("todo")
  })
  it("isStage 识别拖拽目标 id", () => {
    expect(isStage("lost")).toBe(true)
    expect(isStage("negotiation")).toBe(true)
    expect(isStage("opp-1")).toBe(false)
  })
})
