import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

test("商机「出方案」直接发给 AI；回复可复制、点赞点踩会存下来（接口模拟，不调模型、不写库）", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"])
  await loginAs(page, "sales")
  const chats: Record<string, unknown>[] = []
  await page.route("**/api/agent/chat", async (route) => {
    chats.push(route.request().postDataJSON() as Record<string, unknown>)
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: sse("message.delta", { text: "还差几个信息：要几个端？预计多少人用？" }) + sse("done", {}),
    })
  })
  const rates: Record<string, unknown>[] = []
  await page.route("**/api/ai-feedback", async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>
    rates.push(body)
    const data = body.rating ? { message_index: body.message_index, rating: body.rating, comment: body.comment } : null
    await route.fulfill({ json: { code: 0, message: "ok", data } })
  })
  await page.route(/\/api\/ai-feedback\/thread\//, (route) =>
    route.fulfill({ json: { code: 0, message: "ok", data: [] } }),
  )

  await page.goto("/pipeline")
  await page.getByText("合同审查私有化", { exact: true }).first().click()
  await page.getByRole("link", { name: "出方案" }).click()

  // 不用再在输入框里按发送：带着商机直接发出去
  await expect(page.getByText("还差几个信息：要几个端？")).toBeVisible()
  expect(chats).toHaveLength(1)
  expect(chats[0].message).toContain("「合同审查私有化」商机出一份方案")
  expect(chats[0].opportunity_id).toEqual(expect.stringMatching(/^[0-9a-f-]{36}$/))
  expect(chats[0].mode).toBe("work")
  await expect(page).toHaveURL(/\/ai\?t=/)

  await page.getByRole("button", { name: "复制" }).click()
  await expect(page.getByText("已复制")).toBeVisible()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("还差几个信息")

  await page.getByRole("button", { name: "有帮助" }).click()
  await expect(page.getByRole("button", { name: "有帮助" })).toHaveAttribute("aria-pressed", "true")
  await page.getByRole("button", { name: "没帮助" }).click()
  await expect(page.getByRole("button", { name: "没帮助" })).toHaveAttribute("aria-pressed", "true")
  await page.getByRole("textbox", { name: "没帮助的原因" }).fill("应该先看跟进记录")
  await page.getByRole("button", { name: "提交" }).click()
  await expect.poll(() => rates.length).toBe(3)
  expect(rates[0]).toMatchObject({ message_index: 0, rating: "up", mode: "work" })
  expect(rates[0].question).toContain("出一份方案")
  expect(rates[0].answer).toContain("还差几个信息")
  expect(rates[2]).toMatchObject({ rating: "down", comment: "应该先看跟进记录" })
  expect(rates[0].thread_id).toEqual(chats[0].thread_id)

  // 再点一次取消
  await page.getByRole("button", { name: "没帮助" }).click()
  await expect.poll(() => rates.length).toBe(4)
  expect(rates[3].rating).toBeNull()
  await expect(page.getByRole("button", { name: "没帮助" })).toHaveAttribute("aria-pressed", "false")
})
