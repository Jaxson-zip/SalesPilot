import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

const ANSWER =
  "以下内容来自系统内置的示例资料。\n\n提成按合同毛利分档计算（出处：销售提成制度）\n\n可以接着问：\n- 低毛利的合同提成怎么算？\n- 提成什么时候确认？"

test("学习问答：切换模式、引导问题、带 mode 发送、追问建议可点", async ({ page }) => {
  await loginAs(page, "sales")
  // 模拟 SSE：不调模型、不在真实库里建会话
  const bodies: Record<string, unknown>[] = []
  await page.route("**/api/agent/chat", async (route) => {
    bodies.push(route.request().postDataJSON() as Record<string, unknown>)
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: sse("message.delta", { text: ANSWER }) + sse("done", {}),
    })
  })
  await page.goto("/ai")

  await page.getByRole("radio", { name: "学习问答" }).click()
  await expect(page.getByText("刚入职？先了解公司业务")).toBeVisible()
  await expect(page.getByText("示例资料，适合熟悉业务和系统")).toBeVisible()
  // 学习问答只问不做：没有上传材料 / 样例图片
  await expect(page.getByRole("button", { name: /上传材料/ })).toHaveCount(0)

  await page.getByRole("button", { name: /提成怎么算/ }).click()
  await expect(page.getByText("提成按合同毛利分档计算")).toBeVisible()
  expect(bodies[0]).toMatchObject({ mode: "learn", message: "销售提成怎么算？低毛利的合同提成有什么不同？" })
  expect(bodies[0].opportunity_id).toBeUndefined()
  // 对话标题栏也能切换模式，当前是学习问答
  await expect(page.getByRole("radio", { name: "学习问答" })).toHaveAttribute("aria-checked", "true")

  // 「可以接着问」拆成按钮，正文里不再重复显示
  const follow = page.getByRole("button", { name: "提成什么时候确认？" })
  await expect(follow).toBeVisible()
  await expect(page.getByText("可以接着问：")).toHaveCount(0)
  await follow.click()
  await expect.poll(() => bodies.length).toBe(2)
  expect(bodies[1]).toMatchObject({ mode: "learn", message: "提成什么时候确认？" })

  // 点错了：对话中直接切到做方案，另起一个新对话（原对话在历史记录里）
  await page.getByRole("radio", { name: "做方案" }).click()
  await expect(page.getByText("今天要给哪位客户出方案？")).toBeVisible()
  await expect(page.getByRole("radio", { name: "做方案" })).toHaveAttribute("aria-checked", "true")

  // 工作台首页的「学习问答」直接打开学习问答
  await page.goto("/dashboard")
  await page.getByRole("link", { name: "学习问答" }).click()
  await expect(page.getByText("刚入职？先了解公司业务")).toBeVisible()
})
