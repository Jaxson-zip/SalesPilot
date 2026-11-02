import { describe, expect, it } from "vitest"

import { applyAgentEvent, applyDecision, createAssistantTurn, type AssistantTurn } from "@/lib/agent-reducer"
import type { AgentEvent } from "@/types/api"

const run = (events: AgentEvent[], start: AssistantTurn = createAssistantTurn()): AssistantTurn =>
  events.reduce(applyAgentEvent, start)

describe("applyAgentEvent", () => {
  it("工具调用：start 新增运行中步骤，end 改为完成并带摘要", () => {
    const turn = run([
      { event: "tool.start", data: { call_id: "c1", name: "query_catalog", args: { pack: "llm_deploy" } } },
      { event: "tool.end", data: { call_id: "c1", summary: "匹配到 6 个配置" } },
    ])
    expect(turn.steps).toHaveLength(1)
    expect(turn.steps[0]).toMatchObject({ title: "查询产品目录", status: "done", desc: "匹配到 6 个配置" })
  })

  it("工具失败：步骤标为 error，描述里带错误码", () => {
    const turn = run([
      { event: "tool.start", data: { call_id: "c1", name: "generate_quote", args: {} } },
      { event: "tool.error", data: { call_id: "c1", code: 50001, message: "数据库不可用" } },
    ])
    expect(turn.steps[0].status).toBe("error")
    expect(turn.steps[0].desc).toContain("50001")
  })

  it("毛利回退：追加一个 retry 步骤", () => {
    const turn = run([
      { event: "node.retry", data: { node: "check_margin", reason: "经济版毛利 21.8% < 25%", attempt: 1 } },
    ])
    expect(turn.steps[0]).toMatchObject({ status: "retry", title: "毛利校验" })
  })

  it("同类型卡片只保留最新一份（毛利回退后方案卡片不重复）", () => {
    const turn = run([
      { event: "artifact", data: { type: "solution_tiers", data: ["第一次"] } },
      { event: "artifact", data: { type: "bom", data: { v: 1 } } },
      { event: "artifact", data: { type: "solution_tiers", data: ["第二次"] } },
    ])
    expect(turn.artifacts.map((a) => a.type)).toEqual(["solution_tiers", "bom"])
    expect(turn.artifacts[0].data).toEqual(["第二次"])
  })

  it("正文增量按顺序拼接，done 后结束流式", () => {
    const turn = run([
      { event: "message.delta", data: { text: "已为" } },
      { event: "message.delta", data: { text: "你生成三档方案" } },
      { event: "done", data: { thread_id: "t1" } },
    ])
    expect(turn.text).toBe("已为你生成三档方案")
    expect(turn.status).toBe("done")
    expect(turn.endedAt).not.toBeNull()
  })

  it("interrupt：追加等待步骤并显示确认卡片", () => {
    const turn = run([{ event: "interrupt", data: { action: "generate_quote", preview: { total_price: 37200000 } } }])
    expect(turn.interrupt).toMatchObject({ action: "generate_quote", title: "生成报价单" })
    expect(turn.steps.at(-1)?.status).toBe("wait")
  })

  it("error 事件：记录错误码，状态为 error", () => {
    const turn = run([{ event: "error", data: { code: 50401, message: "模型调用超时" } }])
    expect(turn.status).toBe("error")
    expect(turn.error).toEqual({ code: 50401, message: "模型调用超时" })
  })
})

describe("applyDecision", () => {
  it("回归（审查 SP-004）：耗时不含等待确认的时间", () => {
    const waiting = { ...run([{ event: "interrupt", data: { action: "generate_quote", preview: {} } }]) }
    const t0 = 1_000_000
    // 执行了 5 秒后停下等确认，用户 40 分钟后才点取消
    const paused = { ...waiting, startedAt: t0, endedAt: t0 + 5_000 }
    const resumed = applyDecision(paused, "reject", t0 + 2_460_000)
    expect(resumed.endedAt).toBeNull()
    expect(resumed.startedAt).toBe(t0 + 2_455_000)
    // 历史会话里打开的待确认回复（开始 = 结束）：从点击时开始计时
    const restored = { ...waiting, startedAt: t0, endedAt: t0 }
    expect(applyDecision(restored, "reject", t0 + 2_460_000).startedAt).toBe(t0 + 2_460_000)
  })

  it("确认后记录决定；没有 interrupt 时原样返回", () => {
    const plain = createAssistantTurn()
    expect(applyDecision(plain, "approve")).toBe(plain)

    const waiting = run([{ event: "interrupt", data: { action: "submit_expense", preview: {} } }])
    expect(applyDecision(waiting, "approve").interrupt?.decision).toBe("approve")
  })

  it("确认后的续写进 afterText（显示在卡片下面），不再接在卡片上面的正文后", () => {
    const waiting = run([
      { event: "message.delta", data: { text: "我先查一下客户。" } },
      { event: "interrupt", data: { action: "create_task", preview: {} } },
    ])
    const resumed = applyAgentEvent(applyDecision(waiting, "approve"), {
      event: "message.delta",
      data: { text: "已创建提醒任务。" },
    })
    expect(resumed.text).toBe("我先查一下客户。")
    expect(resumed.afterText).toBe("已创建提醒任务。")
  })

  it("同一条回复第二次要确认时，上一段续写并入正文", () => {
    const first = applyAgentEvent(
      applyDecision(run([{ event: "interrupt", data: { action: "approve", preview: {} } }]), "approve"),
      { event: "message.delta", data: { text: "第一条已通过。" } },
    )
    const second = applyAgentEvent(first, { event: "interrupt", data: { action: "approve", preview: {} } })
    expect(second.text).toBe("第一条已通过。")
    expect(second.afterText).toBe("")
    expect(second.interrupt?.decision).toBeUndefined()
  })
})
