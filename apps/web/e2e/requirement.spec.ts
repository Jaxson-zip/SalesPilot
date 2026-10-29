import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const card = {
  pack_id: "software_outsourcing",
  opportunity_id: null,
  requirement: {
    project: "健身房会员约课小程序",
    platforms: ["mini_program", "admin"],
    modules: [
      { key: "account", name: "会员注册登录", complexity: "simple", must: true, source: "inferred" },
      { key: "booking", name: "在线约课排期", complexity: "medium", must: true, source: "mentioned" },
      { key: "custom", name: "会员体测记录", complexity: "medium", must: true, source: "mentioned" },
      { key: "payment", name: "在线支付（课时费）", complexity: "medium", must: false, source: "inferred" },
      { key: "report", name: "约课与出勤统计", complexity: "medium", must: true, source: "inferred" },
    ],
    team_size: null,
    questions: [],
  },
  price_low: 4160000,
  price_high: 18920000,
  inferred: 3,
  questions: ["约课是否需要扣课时 / 会员卡次数？", "教练端和会员端是同一个小程序按角色区分吗？"],
}
const text =
  "根据描述初步拆出 5 个功能模块（其中 3 个是按业务常识补充的，标了「AI 推断」），粗估 **4.2–18.9 万**，可以先给客户这个区间。\n\n正式报价前，建议先和客户确认：\n1. 约课是否需要扣课时 / 会员卡次数？\n2. 教练端和会员端是同一个小程序按角色区分吗？\n\n确认后在下面的需求卡片里增删模块、调整复杂度，点「确认需求，出报价」生成三档正式报价。"

const sse = (events: [string, unknown][]) =>
  events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("")

test("需求卡片：删模块、改个人全栈后确认，请求带上核对后的需求", async ({ page }) => {
  await loginAs(page, "sales")
  const bodies: Record<string, unknown>[] = []
  // 模拟 SSE，不调用模型、不写数据库
  await page.route("**/api/agent/chat", async (route) => {
    bodies.push(route.request().postDataJSON() as Record<string, unknown>)
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body:
        bodies.length === 1
          ? sse([
              ["node.start", { node: "clarify" }],
              ["artifact", { type: "requirement", data: card }],
              ["message.delta", { text }],
              ["done", {}],
            ])
          : sse([
              ["message.delta", { text: "好的，按确认的需求出三档报价。" }],
              ["done", {}],
            ]),
    })
  })
  await page.goto("/ai")
  await page.getByRole("textbox").first().fill("客户是做健身房的，想搞个小程序让会员约课")
  await page.keyboard.press("Enter")
  const cardEl = page.getByRole("region", { name: "需求清单" })
  await expect(cardEl).toBeVisible({ timeout: 15000 })
  await expect(cardEl).toContainText("¥41,600–¥189,200")
  await expect(cardEl.getByText("AI 推断")).toHaveCount(3)

  await cardEl.getByRole("button", { name: "删除 在线支付（课时费）" }).click()
  await cardEl.getByRole("radio", { name: "个人全栈" }).click()
  await cardEl.getByRole("textbox", { name: "补充功能" }).fill("会员积分")
  await cardEl.getByRole("button", { name: "添加" }).click()
  await cardEl.getByRole("button", { name: "确认需求，出报价" }).click()

  await expect.poll(() => bodies.length).toBe(2)
  const req = bodies[1].requirement as { team_size: number; modules: { name: string; source: string }[] }
  expect(req.team_size).toBe(1)
  expect(req.modules.map((m) => m.name)).toEqual([
    "会员注册登录",
    "在线约课排期",
    "会员体测记录",
    "约课与出勤统计",
    "会员积分",
  ])
  expect(req.modules.every((m) => m.source === "mentioned")).toBe(true)
  // 确认后上一张卡片变为只读
  await expect(cardEl.getByRole("button", { name: "确认需求，出报价" })).toHaveCount(0)
})
