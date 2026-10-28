import { expect, test } from "@playwright/test"

import { Api, loginAs, uniq } from "./helpers"

/** 业务补齐（UI与业务审查 B5–B9、U10–U11） */
test.describe("B8 新建客户查重", () => {
  test("输入同名客户：提示已存在并禁止创建；看不到的客户只显示名称和负责人", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/customers")
    await page.getByRole("button", { name: "新建客户" }).click()
    const sheet = page.getByRole("dialog", { name: "新建客户" })
    await sheet.getByLabel("客户名称").fill("鹏城第三人民医院（南山）")
    const hint = sheet.getByRole("status").filter({ hasText: "客户已存在" })
    await expect(hint).toContainText("鹏城第三人民医院")
    await expect(hint).toContainText("联系主管")
    await expect(hint.getByRole("link")).toHaveCount(0) // 销售看不到这个客户，不给链接
    await expect(sheet.getByRole("button", { name: "创建客户" })).toBeDisabled()
  })

  test("输入相近名称：提示可点击的相似客户，仍可创建", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/customers")
    await page.getByRole("button", { name: "新建客户" }).click()
    const sheet = page.getByRole("dialog", { name: "新建客户" })
    await sheet.getByLabel("客户名称").fill("明理律所")
    const hint = sheet.getByRole("status").filter({ hasText: "名称相近" })
    await expect(hint.getByRole("link", { name: "深圳明理律师事务所" })).toBeVisible()
    await expect(sheet.getByRole("button", { name: "创建客户" })).toBeEnabled()
  })
})

test.describe("B7 联系人角色 · U11 客户详情标签页", () => {
  test("客户详情：联系人标签页增删改，商机侧栏显示关键人", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const customer = await api.call<{ id: string }>("POST", "/api/customers", {
      name: uniq("E2E联系人客户"),
      level: "B",
    })
    const opp = await api.call<{ id: string }>("POST", "/api/opportunities", {
      customer_id: customer.id,
      name: uniq("E2E关键人商机"),
      amount: 100_000_00,
      win_rate: 30,
    })
    await loginAs(page, "sales")
    await page.goto(`/customers/${customer.id}`)
    await expect(page.getByRole("tab", { name: "商机" })).toBeVisible()
    await page.getByRole("tab", { name: "联系人" }).click()

    // 新建：选角色「决策人」
    await page.getByRole("button", { name: "添加联系人" }).click()
    const sheet = page.getByRole("dialog", { name: "添加联系人" })
    await sheet.getByLabel("姓名").fill("赵总")
    await sheet.getByLabel("职务").fill("CEO")
    await sheet.getByRole("combobox", { name: "联系人角色" }).click()
    await page.getByRole("option", { name: "决策人" }).click()
    await sheet.getByRole("button", { name: "保存" }).click()
    const list = page.getByRole("list", { name: "联系人列表" })
    await expect(list.getByRole("listitem").filter({ hasText: "赵总" })).toContainText("决策人")

    // 商机侧栏：关键人显示赵总
    await page.goto(`/pipeline?opp=${opp.id}`)
    await expect(page.getByRole("dialog")).toContainText(/关键人\s*赵总\s*决策人/)

    // 编辑角色 → 影响者；再删除
    await page.goto(`/customers/${customer.id}`)
    await page.getByRole("tab", { name: "联系人" }).click()
    await page.getByRole("button", { name: "编辑 赵总" }).click()
    const edit = page.getByRole("dialog", { name: /编辑联系人/ })
    await edit.getByRole("combobox", { name: "联系人角色" }).click()
    await page.getByRole("option", { name: "影响者" }).click()
    await edit.getByRole("button", { name: "保存" }).click()
    await expect(list.getByRole("listitem").filter({ hasText: "赵总" })).toContainText("影响者")
    await page.getByRole("button", { name: "删除 赵总" }).click()
    await page.getByRole("alertdialog").getByRole("button", { name: "确认删除" }).click()
    await expect(page.getByText("还没有联系人")).toBeVisible()

    // 时间线记录了联系人变更
    await page.getByRole("tab", { name: "时间线" }).click()
    await expect(page.getByText("删除了联系人").first()).toBeVisible()
  })

  test("主管查看下属客户：联系人只读", async ({ page }) => {
    await loginAs(page, "manager")
    await page.goto("/customers")
    await page.getByRole("link", { name: "深圳明理律师事务所" }).first().click()
    await page.getByRole("tab", { name: "联系人" }).click()
    await expect(page.getByRole("list", { name: "联系人列表" })).toContainText("王律师")
    await expect(page.getByRole("button", { name: "添加联系人" })).toHaveCount(0)
    await expect(page.getByRole("button", { name: /^编辑 / })).toHaveCount(0)
  })
})

test.describe("B9 回款计划", () => {
  test("合同列表显示下期回款；点编号看三期计划；调整时合计不等不能保存（不改演示数据）", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/contracts")
    const row = page.getByRole("row").filter({ hasText: "C-2026-001" })
    await expect(row).toContainText(/预付款|到货验收款|已收齐/)
    await row.getByRole("button", { name: "C-2026-001" }).click()

    const sheet = page.getByRole("dialog", { name: /回款计划 · C-2026-001/ })
    const table = sheet.getByRole("table", { name: "回款计划" })
    await expect(table.getByRole("row")).toHaveCount(4) // 表头 + 三期
    await expect(table).toContainText("预付款")
    await expect(table).toContainText("已收齐") // 已回款 40%，预付款 30% 收齐

    await sheet.getByRole("button", { name: "调整计划" }).click()
    const first = sheet.getByRole("group", { name: "第 1 期" })
    await first.getByRole("textbox").nth(1).fill("1")
    await expect(sheet.getByText(/还差 ¥/)).toBeVisible()
    await sheet.getByRole("button", { name: "保存计划" }).click()
    await expect(sheet.getByRole("status").filter({ hasText: "还不能保存" })).toContainText("各期合计要等于合同金额")
    await sheet.getByRole("button", { name: "取消" }).click()
    await expect(table).toBeVisible()
  })

  test("主管：回款计划只读", async ({ page }) => {
    await loginAs(page, "manager")
    await page.goto("/contracts")
    await page.getByRole("button", { name: "C-2026-001" }).click()
    const sheet = page.getByRole("dialog", { name: /回款计划/ })
    await expect(sheet.getByRole("table", { name: "回款计划" })).toBeVisible()
    await expect(sheet.getByRole("button", { name: "调整计划" })).toHaveCount(0)
  })
})
