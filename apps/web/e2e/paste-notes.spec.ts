import { expect, test } from "@playwright/test"

import { Api, loginAs } from "./helpers"

const NOTES = "王总：下季度预算已经批了，最关心数据能不能留在本地。\n我：下周三前发两套部署方案。"

test("客户页粘贴纪要 → AI 工作台带着材料和提示语，等销售确认后发送（不调用模型）", async ({ page }) => {
  await loginAs(page, "sales")
  await page.goto("/customers")
  await page.getByRole("link", { name: "深圳明理律师事务所" }).first().click()
  await page.getByRole("button", { name: "粘贴纪要，AI 提炼" }).click()
  const dialog = page.getByRole("dialog", { name: "粘贴纪要，AI 提炼跟进" })
  await expect(dialog.getByRole("button", { name: "交给 AI 提炼" })).toBeDisabled()
  await dialog.getByLabel("沟通纪要").fill(NOTES)
  await dialog.getByRole("button", { name: "交给 AI 提炼" }).click()

  await expect(page).toHaveURL(/\/ai$/)
  await expect(page.getByText("深圳明理律师事务所 沟通纪要.txt")).toBeVisible()
  await expect(page.getByRole("textbox").last()).toHaveValue(/整理成「深圳明理律师事务所」的跟进记录/)
  // 刷新后不会再带一次（暂存只取一次）
  await page.reload()
  await expect(page.getByText("沟通纪要.txt")).toHaveCount(0)
})

test("商机侧栏也能粘贴纪要，提示语带上商机", async ({ page, request }) => {
  // 只读：取销售自己的一个进行中商机
  const api = await Api.as(request, "sales")
  const list = await api.call<{ items: { id: string; name: string; stage: string }[] }>(
    "GET",
    "/api/opportunities?view=mine&page_size=50",
  )
  const opp = list.items.find((o) => !["won", "lost"].includes(o.stage))
  if (!opp) throw new Error("演示数据里张晨没有进行中的商机，请先运行 seed")
  await loginAs(page, "sales")
  await page.goto(`/pipeline?opp=${opp.id}`)
  await page.getByRole("button", { name: "粘贴纪要" }).click()
  await page.getByLabel("沟通纪要").fill(NOTES)
  await page.getByRole("button", { name: "交给 AI 提炼" }).click()
  await expect(page).toHaveURL(/\/ai$/)
  await expect(page.getByRole("textbox").last()).toHaveValue(new RegExp(`「${opp.name}」商机的跟进记录`))
})
