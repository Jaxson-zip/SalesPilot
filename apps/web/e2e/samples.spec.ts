import { expect, test } from "@playwright/test"

import { loginAs } from "./helpers"

const PNG = Buffer.from("89504e470d0a1a0a", "hex")
const reply = (doc: string, fields: string[]) => ({
  code: 0,
  message: "ok",
  data: { name: "x.png", doc_type: doc, fields, quality: "clear" },
})

test("样例图片：逐张识别显示进度，失败的可重试，发送时带上识别结果走出方案", async ({ page }) => {
  await loginAs(page, "sales")
  // 模拟识别接口和 SSE：不调视觉模型、不写数据库
  let failOnce = true
  await page.route("**/api/agent/samples", async (route) => {
    const body = route.request().postDataBuffer()?.toString("latin1") ?? ""
    if (body.includes("c.png") && failOnce) {
      failOnce = false
      await route.fulfill({
        status: 502,
        contentType: "application/json",
        body: JSON.stringify({ code: 50201, message: "图片识别失败，请稍后重试", data: null }),
      })
      return
    }
    const doc = body.includes("b.png") ? "装箱单" : "增值税发票"
    await route.fulfill({ json: reply(doc, doc === "装箱单" ? ["箱号"] : ["发票号码", "金额"]) })
  })
  const chats: Record<string, unknown>[] = []
  await page.route("**/api/agent/chat", async (route) => {
    chats.push(route.request().postDataJSON() as Record<string, unknown>)
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: 'event: message.delta\ndata: {"text":"根据样例初步拆出 4 个功能模块。"}\n\nevent: done\ndata: {}\n\n',
    })
  })

  await page.goto("/ai")
  await page.getByTestId("samples-input").setInputFiles([
    { name: "a.png", mimeType: "image/png", buffer: PNG },
    { name: "b.png", mimeType: "image/png", buffer: PNG },
    { name: "c.png", mimeType: "image/png", buffer: PNG },
  ])
  const chip = page.getByLabel("客户样例图片")
  await expect(chip).toContainText("3 张 · 2 类单据，1 张失败")
  await expect(page.getByRole("button", { name: "发送" })).toBeEnabled()

  await chip.getByRole("button", { name: "重试失败的" }).click()
  await expect(chip).toContainText("3 张 · 2 类单据")
  await expect(chip).not.toContainText("失败")

  await page.getByRole("button", { name: "发送" }).click()
  await expect.poll(() => chats.length).toBe(1)
  const samples = chats[0].samples as { total: number; items: { doc_type: string }[] }
  expect(samples.total).toBe(3)
  expect(samples.items.map((i) => i.doc_type).sort()).toEqual(["增值税发票", "增值税发票", "装箱单"])
  expect(chats[0].message).toContain("按这些客户样例图片出方案")
  // 用户气泡显示样例标签，输入框上方的标签清掉
  await expect(page.getByText("客户样例图片（3 张 · 2 类单据）")).toBeVisible()
  await expect(chip).toHaveCount(0)
})
