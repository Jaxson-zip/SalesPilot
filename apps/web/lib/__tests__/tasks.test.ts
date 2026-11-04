import { describe, expect, it } from "vitest"

import {
  dueDayLabel,
  dueShortcutDate,
  dueText,
  isTaskOverdue,
  mergeTodoTasks,
  nextStepView,
  staleText,
  taskHref,
  taskSubjectHref,
  toDueIso,
  todoSummary,
} from "@/lib/tasks"

// 2026-10-26 是周一
const pad = (n: number) => String(n).padStart(2, "0")
/** 北京时间的时刻（测试与运行环境的时区无关） */
const bj = (y: number, m: number, d: number, h = 10, mi = 0) =>
  new Date(`${y}-${pad(m)}-${pad(d)}T${pad(h)}:${pad(mi)}:00+08:00`)
const MON = bj(2026, 10, 26, 9, 30)
const iso = (y: number, m: number, d: number, h = 10, mi = 0) => bj(y, m, d, h, mi).toISOString()

describe("到期快捷选项", () => {
  it("今天 / 明天", () => {
    expect(dueShortcutDate("today", MON)).toBe("2026-10-26")
    expect(dueShortcutDate("tomorrow", MON)).toBe("2026-10-27")
  })
  it("下周一：周一 → 7 天后；周日 → 明天；周三 → 下周一", () => {
    expect(dueShortcutDate("next_monday", MON)).toBe("2026-11-02")
    expect(dueShortcutDate("next_monday", bj(2026, 11, 1))).toBe("2026-11-02")
    expect(dueShortcutDate("next_monday", bj(2026, 10, 28))).toBe("2026-11-02")
  })
  it("跨月", () => {
    expect(dueShortcutDate("tomorrow", bj(2026, 10, 31))).toBe("2026-11-01")
  })
})

// 回归：浏览器在海外时区（太平洋时间 11-03 08:35 = 北京 11-04 00:35）时，「今天」取成了 11-03，和后端差一天
describe("按北京时间算日期，与浏览器时区无关", () => {
  const pacificMorning = new Date("2026-11-03T08:35:00-08:00")
  it("今天 / 明天取北京日期", () => {
    expect(dueShortcutDate("today", pacificMorning)).toBe("2026-11-04")
    expect(dueShortcutDate("tomorrow", pacificMorning)).toBe("2026-11-05")
  })
  it("到期文案按北京时间的日期和钟点", () => {
    expect(dueText(iso(2026, 11, 4, 10, 0), false, pacificMorning)).toBe("今天 10:00")
    expect(dueDayLabel(iso(2026, 11, 3, 23, 0), pacificMorning)).toBe("昨天")
  })
  it("填的时间按北京时间理解", () => {
    expect(toDueIso("2026-11-04", "10:00")).toBe("2026-11-04T02:00:00.000Z")
  })
})

describe("toDueIso", () => {
  it("业务日期 + 时间 → ISO", () => {
    expect(toDueIso("2026-10-27", "15:30")).toBe(iso(2026, 10, 27, 15, 30))
  })
  it("时间为空用默认 10:00；格式不对返回 null", () => {
    expect(toDueIso("2026-10-27", "")).toBe(iso(2026, 10, 27, 10, 0))
    expect(toDueIso("2026/10/27", "10:00")).toBeNull()
    expect(toDueIso("2026-10-27", "25:00")).toBeNull()
  })
})

describe("到期文案", () => {
  it("今天 / 明天 / 昨天 / 周X / MM-DD", () => {
    expect(dueDayLabel(iso(2026, 10, 26), MON)).toBe("今天")
    expect(dueDayLabel(iso(2026, 10, 27), MON)).toBe("明天")
    expect(dueDayLabel(iso(2026, 10, 25), MON)).toBe("昨天")
    expect(dueDayLabel(iso(2026, 10, 30), MON)).toBe("周五")
    expect(dueDayLabel(iso(2026, 11, 20), MON)).toBe("11-20")
    expect(dueDayLabel(iso(2027, 1, 5), MON)).toBe("2027-01-05")
  })
  it("带时间；逾期显示「已逾期」", () => {
    expect(dueText(iso(2026, 10, 27, 15, 0), false, MON)).toBe("明天 15:00")
    expect(dueText(iso(2026, 10, 24), true, MON)).toBe("已逾期 · 10-24")
  })
  it("逾期以后端为准，没给时按当前时间判断；已完成不算逾期", () => {
    expect(isTaskOverdue({ due_at: iso(2026, 10, 20), overdue: false }, MON)).toBe(false)
    expect(isTaskOverdue({ due_at: iso(2026, 10, 20) }, MON)).toBe(true)
    expect(isTaskOverdue({ due_at: iso(2026, 10, 20), done: true }, MON)).toBe(false)
  })
})

describe("商机卡片的下一步（v3 §12）", () => {
  it("有任务：「下一步：xxx · 明天」，逾期标红", () => {
    const v = nextStepView(
      { stage: "proposal", next_task: { id: "t", title: "电话确认", due_at: iso(2026, 10, 27), overdue: false } },
      MON,
    )
    expect(v).toEqual({ kind: "task", text: "下一步：电话确认 · 明天", overdue: false })
  })
  it("未终态且没有下一步 → missing（淡黄色提示）", () => {
    expect(nextStepView({ stage: "lead", next_task: null }, MON)).toEqual({ kind: "missing" })
  })
  it("终态或后端还没返回字段 → 不显示", () => {
    expect(nextStepView({ stage: "won", next_task: null }, MON).kind).toBe("hidden")
    expect(nextStepView({ stage: "lead" }, MON).kind).toBe("hidden")
  })
})

describe("停滞文案（v3 §13）", () => {
  it("stale 才显示", () => {
    expect(staleText({ stale: true, idle_days: 21 })).toBe("已 21 天未跟进")
    expect(staleText({ stale: true })).toBe("长时间未跟进")
    expect(staleText({ stale: false, idle_days: 30 })).toBeNull()
    expect(staleText({})).toBeNull()
  })
})

describe("工作台待办", () => {
  it("逾期在前、按到期时间排序、去重", () => {
    const a = { id: "a", due_at: iso(2026, 10, 24) }
    const b = { id: "b", due_at: iso(2026, 10, 20) }
    const c = { id: "c", due_at: iso(2026, 10, 26, 15) }
    const d = { id: "d", due_at: iso(2026, 10, 26, 9) }
    expect(mergeTodoTasks([a, b], [c, d, a]).map((t) => t.id)).toEqual(["b", "a", "d", "c"])
  })
  it("标题跳转：商机 → 看板打开侧栏；客户 → 详情", () => {
    expect(taskSubjectHref({ subject_type: "opportunity", subject_id: "o 1" })).toBe("/pipeline?opp=o%201")
    expect(taskSubjectHref({ subject_type: "customer", subject_id: "c1" })).toBe("/customers/c1")
  })
  it("点任务：定位到这条任务", () => {
    expect(taskHref({ id: "t1", subject_type: "opportunity", subject_id: "o1" })).toBe("/pipeline?opp=o1&task=t1")
    expect(taskHref({ id: "t 2", subject_type: "customer", subject_id: "c1" })).toBe("/customers/c1?task=t%202")
  })
  it("标题摘要", () => {
    expect(todoSummary(undefined, undefined)).toBe("")
    expect(todoSummary(3, 0)).toBe("今天 3 项待办")
    expect(todoSummary(3, 2)).toBe("今天 3 项待办，2 项已逾期")
  })
})
