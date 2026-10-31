import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

test("记跟进：先出确认卡；确认后按执行结果显示「已完成」和记录入口（模拟 SSE，不写库）", async ({ page }) => {
  await loginAs(page, "sales")
  await page.route("**/api/agent/chat", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: [
        sse("message.delta", { text: "我来给明理记一条电话跟进。" }),
        sse("interrupt", {
          action: "add_followup",
          preview: { customer_name: "深圳明理律师事务所", content: "电话沟通方案" },
        }),
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
      body: [
        sse("message.delta", { text: "请确认卡片，确认后即写入系统。" }),
        sse("artifact", {
          type: "action_result",
          data: { action: "add_followup", status: "done", summary: "已记录跟进", href: "/customers/abc" },
        }),
        sse("message.replace", { text: "已完成：已记录跟进。" }),
        sse("done", {}),
      ].join(""),
    })
  })

  await page.goto("/ai")
  await page.getByRole("textbox").first().fill("给明理记录电话跟进，请先给确认卡片")
  await page.getByRole("button", { name: "发送" }).click()
  await page.getByRole("button", { name: "确认执行" }).click()
  await expect.poll(() => resumes.length).toBe(1)

  const status = page.getByRole("status").filter({ hasText: "已完成：已记录跟进" })
  await expect(status).toBeVisible()
  await expect(status.getByRole("link", { name: "查看" })).toHaveAttribute("href", "/customers/abc")
  await expect(page.getByText("已完成：已记录跟进。")).toBeVisible()
  await expect(page.getByText("请确认卡片，确认后即写入系统。")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "确认执行" })).toHaveCount(0)
  if (process.env.SHOT_DIR) await page.screenshot({ path: `${process.env.SHOT_DIR}/action-result.png`, fullPage: true })
})
