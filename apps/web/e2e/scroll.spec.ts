import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

const tier = (name: string, price: number, recommended = false) => ({
  name,
  summary: `${name}：2 台推理服务器，vLLM 部署，含运维监控与 1 年维保`,
  total_price: price,
  total_cost: Math.round(price * 0.7),
  margin_rate: 0.3,
  recommended,
  items: Array.from({ length: 12 }, (_, i) => ({
    sku: `SKU-${i}`,
    name: `物料 ${i + 1}`,
    category: "service",
    unit: "项",
    qty: 1,
    unit_cost: 700_000,
    unit_price: 1_000_000,
  })),
})

test("出方案：三档方案卡出来后停在卡片顶部，不被下面的物料清单和确认卡顶出视口", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 })
  await loginAs(page, "sales")
  // 模拟 SSE（与真实出方案顺序一致）：说明 → 三档方案 → 推荐档物料清单 → 确认卡；不调模型、不写库
  const recommended = tier("标准版", 36_000_000, true)
  const body = [
    sse("message.delta", { text: "根据需求给出三档方案：" }),
    sse("artifact", {
      type: "solution_tiers",
      data: [tier("经济版", 28_600_000), recommended, tier("旗舰版", 81_000_000)],
    }),
    sse("artifact", { type: "bom", data: recommended }),
    sse("interrupt", { action: "create_quote", preview: { customer_name: "南山教育集团", tier_name: "标准版" } }),
    sse("done", {}),
  ].join("")
  await page.route("**/api/agent/chat", (route) =>
    route.fulfill({ status: 200, headers: { "content-type": "text/event-stream" }, body }),
  )

  await page.goto("/ai")
  await page.getByRole("textbox").first().fill("给南山教育集团出一份方案")
  await page.getByRole("button", { name: "发送" }).click()
  await expect(page.getByText("物料 12").first()).toBeAttached()
  await page.waitForTimeout(300)
  // 三档的名字都在视口里（旧逻辑一直滚到底，方案卡被顶到上面）
  for (const name of ["经济版", "旗舰版"]) {
    await expect(page.getByText(name, { exact: true }).first()).toBeInViewport()
  }
})
