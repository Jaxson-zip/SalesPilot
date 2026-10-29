import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

const tier = (key: string, name: string, price: number, item: string, recommended = false) => ({
  tier: key,
  name,
  summary: `${name}配置说明`,
  total_price: price,
  total_cost: Math.round(price * 0.7),
  margin_rate: 0.3,
  recommended,
  items: [{ sku: `SKU-${key}`, name: item, category: "hardware", unit: "台", qty: 1, unit_cost: 1, unit_price: 2 }],
})

test("出方案：点选经济版后物料清单和确认卡跟着切换，确认时带上所选档位", async ({ page }) => {
  await loginAs(page, "sales")
  const standard = tier("standard", "标准版", 36_000_000, "标准版服务器", true)
  const tiers = [
    tier("economy", "经济版", 28_600_000, "经济版服务器"),
    standard,
    tier("flagship", "旗舰版", 81_000_000, "旗舰版服务器"),
  ]
  const preview = {
    customer_name: "南山教育集团",
    tier: "standard",
    name: "标准版",
    summary: "标准版配置说明",
    total_price: 36_000_000,
    margin_rate: 0.3,
  }
  // 模拟 SSE，不调模型、不写库；记下确认请求的请求体
  await page.route("**/api/agent/chat", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: [
        sse("message.delta", { text: "给出三档方案：" }),
        sse("artifact", { type: "solution_tiers", data: tiers }),
        sse("artifact", { type: "bom", data: standard }),
        sse("interrupt", { action: "generate_quote", preview }),
        sse("done", {}),
      ].join(""),
    }),
  )
  const resumes: Record<string, unknown>[] = []
  await page.route("**/api/agent/resume", async (route) => {
    resumes.push(route.request().postDataJSON() as Record<string, unknown>)
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: sse("message.delta", { text: "已按经济版生成报价单。" }) + sse("done", {}),
    })
  })

  await page.goto("/ai")
  await page.getByRole("textbox").first().fill("给南山教育集团出一份方案")
  await page.getByRole("button", { name: "发送" }).click()

  const economy = page.getByRole("button", { name: "选择经济版" })
  await expect(page.getByRole("button", { name: "选择标准版" })).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByText("标准版服务器").first()).toBeVisible()
  await economy.click()
  await expect(economy).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByText("经济版服务器").first()).toBeVisible()
  await expect(page.getByText("标准版服务器")).toHaveCount(0)
  await expect(page.getByText("¥286,000").last()).toBeVisible() // 确认卡里的报价跟着变

  await page.getByRole("button", { name: "确认执行" }).click()
  await expect.poll(() => resumes.length).toBe(1)
  expect(resumes[0]).toMatchObject({ decision: "approve", tier: "economy" })
  // 确认后不能再切换
  await expect(page.getByRole("button", { name: "选择旗舰版" })).toHaveCount(0)
})
