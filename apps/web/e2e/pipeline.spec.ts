import { expect, test } from "@playwright/test"

import { Api, dragTo, loginAs, uniq } from "./helpers"

interface Customer {
  id: string
  name: string
}
interface Opportunity {
  id: string
  name: string
  stage: string
  lost_reason?: string | null
}

async function newLeadOpportunity(api: Api): Promise<Opportunity> {
  const customers = await api.call<{ items: Customer[] }>("GET", "/api/customers?view=mine&q=深圳明理&page_size=50")
  const mingli = customers.items.find((c) => c.name === "深圳明理律师事务所")
  if (!mingli) throw new Error("演示数据缺少深圳明理律师事务所，请先运行 seed")
  return api.call<Opportunity>("POST", "/api/opportunities", {
    customer_id: mingli.id,
    name: uniq("拖拽测试"),
    amount: 10_000_000,
  })
}

test.describe("商机看板", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "sales")
  })

  test("把卡片从「线索」拖到「需求确认」，阶段写入后端并留在新列", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const opp = await newLeadOpportunity(api)

    await page.goto("/pipeline")
    const lead = page.locator('[data-stage="lead"]')
    const qualified = page.locator('[data-stage="qualified"]')
    const card = lead.getByText(opp.name, { exact: true })
    await expect(card).toBeVisible()

    await dragTo(page, card, qualified)

    await expect(qualified.getByText(opp.name, { exact: true })).toBeVisible()
    await expect(lead.getByText(opp.name, { exact: true })).toHaveCount(0)
    await expect
      .poll(async () => (await api.call<Opportunity>("GET", `/api/opportunities/${opp.id}`)).stage)
      .toBe("qualified")

    // 刷新后仍在新列：说明不是只改了前端缓存
    await page.reload()
    await expect(page.locator('[data-stage="qualified"]').getByText(opp.name, { exact: true })).toBeVisible()
  })

  test("拖到「输单」区域弹出原因弹窗：原因必填，确认后标记为输单", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const opp = await newLeadOpportunity(api)

    await page.goto("/pipeline")
    const card = page.locator('[data-stage="lead"]').getByText(opp.name, { exact: true })
    await expect(card).toBeVisible()
    await dragTo(page, card, page.getByText("拖到这里标记为「输单」"))

    const dialog = page.getByRole("dialog", { name: "标记为输单" })
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText(opp.name)
    const confirm = dialog.getByRole("button", { name: "确认输单" })
    await expect(confirm).toBeDisabled()

    await dialog.getByRole("textbox").fill("客户预算削减，选择了价格更低的竞品")
    await expect(confirm).toBeEnabled()
    await confirm.click()

    await expect(dialog).toBeHidden()
    await expect(page.locator("[data-stage]").getByText(opp.name, { exact: true })).toHaveCount(0)
    const saved = await api.call<Opportunity>("GET", `/api/opportunities/${opp.id}`)
    expect(saved.stage).toBe("lost")
    expect(saved.lost_reason).toBe("客户预算削减，选择了价格更低的竞品")
  })

  test("输单弹窗点取消：商机留在原阶段", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const opp = await newLeadOpportunity(api)

    await page.goto("/pipeline")
    const lead = page.locator('[data-stage="lead"]')
    await dragTo(page, lead.getByText(opp.name, { exact: true }), page.getByText("拖到这里标记为「输单」"))
    const dialog = page.getByRole("dialog", { name: "标记为输单" })
    await dialog.getByRole("button", { name: "取消", exact: true }).click()

    await expect(dialog).toBeHidden()
    await expect(lead.getByText(opp.name, { exact: true })).toBeVisible()
    expect((await api.call<Opportunity>("GET", `/api/opportunities/${opp.id}`)).stage).toBe("lead")
  })

  test("误拖后点「撤销」：恢复到原阶段（回归：曾经点错不能撤销）", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const opp = await newLeadOpportunity(api)

    await page.goto("/pipeline")
    await dragTo(
      page,
      page.locator('[data-stage="lead"]').getByText(opp.name, { exact: true }),
      page.locator('[data-stage="qualified"]'),
    )
    const undo = page.getByRole("button", { name: "撤销" })
    await expect(undo).toBeVisible()
    await expect
      .poll(async () => (await api.call<Opportunity>("GET", `/api/opportunities/${opp.id}`)).stage)
      .toBe("qualified")

    await undo.click()
    await expect(page.getByText(/已撤销/)).toBeVisible()
    await expect(page.locator('[data-stage="lead"]').getByText(opp.name, { exact: true })).toBeVisible()
    expect((await api.call<Opportunity>("GET", `/api/opportunities/${opp.id}`)).stage).toBe("lead")
  })

  test("拖到「赢单」要先确认（无报价时不能赢单、不显示确认按钮）；点取消阶段不变", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const opp = await newLeadOpportunity(api)

    await page.goto("/pipeline")
    await dragTo(
      page,
      page.locator('[data-stage="lead"]').getByText(opp.name, { exact: true }),
      page.locator('[data-stage="won"]'),
    )
    const dialog = page.getByRole("dialog", { name: "标记为赢单" })
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText("赢单需要按已审批或已发送的报价成交") // 没有报价时明确告知
    await expect(dialog.getByRole("button", { name: /确认/ })).toHaveCount(0) // 不放点了也会失败的按钮
    await dialog.getByRole("button", { name: "取消", exact: true }).click()

    await expect(dialog).toBeHidden()
    await expect(page.locator('[data-stage="lead"]').getByText(opp.name, { exact: true })).toBeVisible()
    expect((await api.call<Opportunity>("GET", `/api/opportunities/${opp.id}`)).stage).toBe("lead")
  })
})
