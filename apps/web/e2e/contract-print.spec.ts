import { expect, test } from "@playwright/test"

import { Api, loginAs } from "./helpers"

test("从回款计划打开合同要素确认单：双方、金额大写、回款计划、签字栏（只读）", async ({ page, request }) => {
  const api = await Api.as(request, "sales")
  const list = await api.call<{ items: { id: string; code: string; customer: { name: string } | null }[] }>(
    "GET",
    "/api/contracts?page_size=1",
  )
  const c = list.items[0]
  if (!c) throw new Error("演示数据里没有合同，请先运行 seed")
  await loginAs(page, "sales")
  await page.goto(`/contracts?plan=${c.id}`)
  await page.getByRole("link", { name: "打印合同要素确认单" }).click()

  await expect(page).toHaveURL(new RegExp(`/contracts/${c.id}/print$`))
  await expect(page.getByText("合同要素确认单", { exact: true })).toBeVisible()
  await expect(page.getByText(c.code, { exact: true })).toBeVisible()
  if (c.customer) await expect(page.getByText(c.customer.name).first()).toBeVisible()
  await expect(page.getByText(/^[零壹贰叁肆伍陆柒捌玖拾佰仟万亿元角分整]+$/).first()).toBeVisible()
  await expect(page.getByRole("region", { name: "回款计划" })).toBeVisible()
  await expect(page.getByRole("region", { name: "确认单说明" })).toContainText("正式合同")
  await expect(page.getByText("甲方（盖章）")).toBeVisible()
  await expect(page).toHaveTitle(new RegExp(`^合同要素确认单-${c.code}`))
  await page.getByRole("link", { name: "返回合同" }).click()
  await expect(page).toHaveURL(/\/contracts/)
})

test("合同要素确认单附带需求范围说明书（PRD），可以取消勾选（模拟 PRD 接口，只读）", async ({ page, request }) => {
  const api = await Api.as(request, "sales")
  const list = await api.call<{ items: { id: string; quote: { id: string } | null }[] }>(
    "GET",
    "/api/contracts?page_size=50",
  )
  let target: string | null = null
  for (const c of list.items) {
    if (!c.quote) continue
    const q = await api.call<{ opportunity: { id: string } | null }>("GET", `/api/quotes/${c.quote.id}`)
    if (q.opportunity) {
      target = c.id
      break
    }
  }
  if (!target) throw new Error("演示数据里没有关联商机的合同，请先运行 seed")
  await page.route("**/api/opportunities/*/requirement/prd", (route) =>
    route.fulfill({
      json: {
        code: 0,
        message: "ok",
        data: {
          markdown:
            "# 预约小程序 需求规格说明书\n\n> AI 生成的草案，需确认。\n\n## 2 交付范围\n\n在线预约（首期）——预约时段（待确认）\n",
          source: "ai",
          generated_at: "2026-10-29T08:00:00Z",
          generated_by: "张晨",
          requirement_at: "2026-10-29T08:00:00Z",
          confirmed: true,
          stale: true,
        },
      },
    }),
  )
  // 报价时单列的客户自付费用：合同里写明不含在合同金额内
  await page.route(/\/api\/quotes\/[^/?]+$/, async (route) => {
    const res = await route.fetch()
    const body = await res.json()
    body.data.client_costs = [{ name: "云服务器", amount: 300000, period: "year", note: "以客户主体开通" }]
    await route.fulfill({ response: res, json: body })
  })
  await loginAs(page, "sales")
  await page.goto(`/contracts/${target}/print`)
  const costs = page.getByRole("region", { name: "客户自付费用" })
  await expect(costs).toContainText("不含在合同金额内")
  await expect(costs).toContainText("/年")
  const appendix = page.getByRole("region", { name: "附件一 需求范围说明书" })
  await expect(appendix).toContainText("在线预约（首期）")
  await expect(appendix).not.toContainText("AI 生成的草案")
  // 打印前提示（不打印）：PRD 过期、还有待确认项
  await expect(appendix.getByText("需求清单又改过")).toBeVisible()
  await expect(appendix.getByText("还有 1 处「待确认」")).toBeVisible()
  await page.getByRole("checkbox", { name: "附带需求范围说明书" }).click()
  await expect(appendix).toHaveCount(0)
})
