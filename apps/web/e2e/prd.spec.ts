import { expect, test } from "@playwright/test"

import { Api, loginAs } from "./helpers"

const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

const REQUIREMENT = {
  pack: "software_outsourcing",
  data: {
    platforms: ["mini_program", "admin"],
    modules: [{ key: "booking", name: "在线预约", complexity: "complex", must: true, source: "mentioned" }],
  },
  confirmed: true,
  questions: [],
  updated_at: "2026-10-29T08:00:00Z",
}

const PRD = {
  markdown:
    "# 预约小程序 需求规格说明书\n\n> AI 生成的草案\n\n## 2 交付范围\n\n| 模块 | 阶段 |\n|---|---|\n| 在线预约 | 首期 |\n",
  source: "ai",
  generated_at: "2026-10-29T08:01:00Z",
  generated_by: "张晨",
  requirement_at: "2026-10-29T08:00:00Z",
  confirmed: true,
  stale: false,
}

test("商机侧栏：生成 PRD 规格书（流式）、预览表格、复制和下载（模拟接口，不调模型、不写库）", async ({
  page,
  request,
  context,
}) => {
  const api = await Api.as(request, "sales")
  const list = await api.call<{ items: { id: string; stage: string }[] }>(
    "GET",
    "/api/opportunities?view=mine&page_size=50",
  )
  const opp = list.items.find((o) => !["won", "lost"].includes(o.stage))
  if (!opp) throw new Error("演示数据里张晨没有进行中的商机，请先运行 seed")
  await context.grantPermissions(["clipboard-read", "clipboard-write"])
  await page.route(`**/api/opportunities/${opp.id}/requirement`, (route) =>
    route.fulfill({ json: { code: 0, message: "ok", data: REQUIREMENT } }),
  )
  let generated = false
  await page.route(`**/api/opportunities/${opp.id}/requirement/prd`, async (route) => {
    if (route.request().method() === "POST") {
      generated = true
      await route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: [
          sse("message.delta", { text: "# 预约小程序 需求规格说明书\n\n" }),
          sse("artifact", { type: "prd", data: PRD }),
          sse("done", {}),
        ].join(""),
      })
    } else {
      await route.fulfill({ json: { code: 0, message: "ok", data: generated ? PRD : null } })
    }
  })

  await loginAs(page, "sales")
  await page.goto(`/pipeline?opp=${opp.id}`)
  await page.getByRole("button", { name: "PRD 规格书" }).click()
  const dialog = page.getByRole("dialog", { name: "PRD 规格书" })
  await expect(dialog.getByText("还没有生成 PRD")).toBeVisible()
  await expect(dialog.getByRole("button", { name: "下载 .md" })).toBeDisabled()

  await dialog.getByRole("button", { name: "生成 PRD" }).click()
  const preview = dialog.getByLabel("PRD 预览")
  await expect(preview.getByRole("cell", { name: "在线预约" })).toBeVisible()
  await expect(dialog.getByText(/AI 扩写 · 张晨/)).toBeVisible()
  await expect(dialog.getByRole("button", { name: "重新生成" })).toBeVisible()

  await dialog.getByRole("button", { name: "复制 Markdown" }).click()
  // Windows 剪贴板会把换行转成 CRLF
  const copied = await page.evaluate(() => navigator.clipboard.readText())
  expect(copied.replaceAll("\r\n", "\n")).toBe(PRD.markdown)
  const download = page.waitForEvent("download")
  await dialog.getByRole("button", { name: "下载 .md" }).click()
  expect((await download).suggestedFilename()).toMatch(/-PRD规格书\.md$/)
})
