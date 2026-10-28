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

test.describe("U10 行内编辑", () => {
  test("客户字段：点值编辑，回车保存，刷新后仍在；金额格式错误不提交", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const customer = await api.call<{ id: string }>("POST", "/api/customers", { name: uniq("E2E行内编辑"), level: "C" })
    await loginAs(page, "sales")
    await page.goto(`/customers/${customer.id}`)

    await page.getByRole("button", { name: "编辑地址" }).click()
    await page.getByRole("textbox", { name: "地址" }).fill("深圳市南山区科技园")
    await page.keyboard.press("Enter")
    await expect(page.getByRole("button", { name: "编辑地址" })).toHaveText("深圳市南山区科技园")

    await page.getByRole("button", { name: "编辑年度预算" }).click()
    const budget = page.getByRole("textbox", { name: "年度预算" })
    await budget.fill("abc")
    await page.keyboard.press("Enter")
    await expect(page.getByText("请输入金额，最多两位小数")).toBeVisible()
    await budget.fill("500000")
    await page.keyboard.press("Enter")
    await expect(page.getByRole("button", { name: "编辑年度预算" })).toHaveText("¥500,000")

    await page.getByRole("button", { name: "编辑等级" }).click()
    await page.getByRole("combobox", { name: "等级" }).click()
    await page.getByRole("option", { name: "A 级（重点客户）" }).click()
    await expect(page.getByRole("button", { name: "编辑等级" })).toHaveText("A")

    await page.reload()
    await expect(page.getByRole("button", { name: "编辑地址" })).toHaveText("深圳市南山区科技园")
    await expect(page.getByRole("button", { name: "编辑年度预算" })).toHaveText("¥500,000")
  })

  test("商机侧栏：改金额和赢率，Esc 取消不关侧栏；主管只读", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const customer = await api.call<{ id: string }>("POST", "/api/customers", { name: uniq("E2E商机编辑"), level: "B" })
    const opp = await api.call<{ id: string }>("POST", "/api/opportunities", {
      customer_id: customer.id,
      name: uniq("E2E行内商机"),
      amount: 100_000_00,
      win_rate: 30,
    })
    await loginAs(page, "sales")
    await page.goto(`/pipeline?opp=${opp.id}`)
    const sheet = page.getByRole("dialog")

    await sheet.getByRole("button", { name: "编辑赢率" }).click()
    await sheet.getByRole("textbox", { name: "赢率" }).fill("120")
    await page.keyboard.press("Enter")
    await expect(sheet.getByText("请输入 0–100 的整数")).toBeVisible()
    await page.keyboard.press("Escape")
    await expect(sheet).toBeVisible() // Esc 只退出编辑
    await expect(sheet.getByRole("button", { name: "编辑赢率" })).toHaveText("30%")

    await sheet.getByRole("button", { name: "编辑金额" }).click()
    await sheet.getByRole("textbox", { name: "金额" }).fill("150000")
    await page.keyboard.press("Enter")
    await expect(sheet.getByRole("button", { name: "编辑金额" })).toHaveText("¥150,000")
    expect((await api.call<{ amount: number }>("GET", `/api/opportunities/${opp.id}`)).amount).toBe(150_000_00)

    await loginAs(page, "manager")
    await page.goto(`/pipeline?opp=${opp.id}`)
    await expect(page.getByRole("dialog")).toContainText("¥150,000")
    await expect(page.getByRole("button", { name: "编辑金额" })).toHaveCount(0)
  })
})

test.describe("B5 客户公海", () => {
  test("退回公海要写原因；公海视图能看到；主管只读；销售领取后恢复可编辑", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const name = uniq("E2E公海客户")
    const customer = await api.call<{ id: string }>("POST", "/api/customers", { name, level: "C" })
    await loginAs(page, "sales")
    await page.goto(`/customers/${customer.id}`)

    await page.getByRole("button", { name: "退回公海" }).click()
    const dialog = page.getByRole("dialog", { name: "退回公海" })
    await expect(dialog.getByRole("button", { name: "确认退回" })).toBeDisabled()
    await dialog.getByRole("button", { name: "长期联系不上" }).click()
    await dialog.getByRole("button", { name: "确认退回" }).click()
    await expect(page.getByText("公海客户", { exact: true })).toBeVisible()
    await expect(page.getByRole("button", { name: "编辑地址" })).toHaveCount(0)
    await expect(page.getByRole("button", { name: "写跟进" })).toHaveCount(0)

    await page.goto("/customers")
    await page.getByRole("button", { name: /我的客户/ }).click()
    await page.getByRole("menuitemradio", { name: "公海" }).click()
    await expect(page.getByRole("row").filter({ hasText: name })).toBeVisible()

    await loginAs(page, "manager")
    await page.goto(`/customers/${customer.id}`)
    await expect(page.getByText("转移负责人", { exact: false })).toBeVisible()
    await expect(page.getByRole("button", { name: "领取客户" })).toHaveCount(0)

    await loginAs(page, "sales")
    await page.goto(`/customers/${customer.id}`)
    await page.getByRole("button", { name: "领取客户" }).click()
    await expect(page.getByRole("button", { name: "编辑地址" })).toBeVisible()
    await expect(page.getByRole("button", { name: "退回公海" })).toBeVisible()
  })
})

test.describe("AI 工作台会话记录（右侧面板）", () => {
  test("左侧导航不混入会话；标题行打开面板，搜索、点一条打开并写进地址、自动关闭；新对话回到欢迎页", async ({
    page,
    request,
  }) => {
    const api = await Api.as(request, "sales")
    const thread = `pw-${Date.now().toString(36)}`
    await api.sse("/api/agent/chat", { thread_id: thread, message: "出差住宿的报销标准是多少？" })
    await loginAs(page, "sales")
    await page.goto("/ai")
    const panel = page.getByRole("navigation", { name: "会话记录" })
    await expect(panel).toHaveCount(0) // 默认不占位置

    await page.getByRole("button", { name: "历史记录" }).click()
    await expect(panel).toBeVisible()
    await page.getByRole("textbox", { name: "搜索会话" }).fill("出差住宿")
    await expect(panel.getByRole("link", { name: /给明理律所/ })).toHaveCount(0)
    await panel
      .getByRole("link", { name: /出差住宿的报销标准/ })
      .first()
      .click()
    await expect(panel).toBeHidden()
    await expect(page).toHaveURL(/\/ai\?t=/)
    await expect(page.getByText("出差住宿的报销标准是多少？").last()).toBeVisible()

    await page.reload() // 刷新后按地址恢复会话
    await expect(page.getByText("出差住宿的报销标准是多少？").last()).toBeVisible()

    await page.getByRole("button", { name: "历史记录" }).click()
    await page.getByRole("dialog").getByRole("link", { name: "新对话" }).click()
    await expect(page).toHaveURL(/\/ai$/)
    await expect(page.getByText("今天要给哪位客户出方案？")).toBeVisible()

    await page.setViewportSize({ width: 390, height: 844 })
    await page.reload()
    await expect(page.getByText("今天要给哪位客户出方案？")).toBeInViewport() // 欢迎页顶部不被裁掉
    await page.getByRole("button", { name: "历史记录" }).click()
    await expect(panel).toBeVisible()
  })

  test("出方案：说明文字先逐字出来，方案卡片和确认框随后出现", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/ai")
    await page
      .getByRole("textbox")
      .first()
      .fill("给明理律所出一份 Qwen3-32B 私有化方案，50 人并发，做合同审查，预算 40 万以内")
    await page.keyboard.press("Enter")
    await expect(page).toHaveURL(/\/ai\?t=/) // 新会话写进地址
    const confirm = page.getByRole("button", { name: "确认执行" })
    // 说明正文出现时确认框还没出来（逐字显示 + 卡片等文字显示完）
    await expect(page.locator(".prose-chat").first()).toBeVisible({ timeout: 60_000 })
    expect(await confirm.count()).toBe(0)
    await expect(confirm).toBeVisible({ timeout: 60_000 })
    await expect(page.locator(".prose-chat").first()).toContainText("推荐")
  })
})

test.describe("审查 v6 待定项", () => {
  test("会话记录：显示时间，可以改名和删除", async ({ page, request }) => {
    const api = await Api.as(request, "sales")
    const thread = `pw-${Date.now().toString(36)}`
    await api.sse("/api/agent/chat", { thread_id: thread, message: "公司一年有几天年假？" })
    await loginAs(page, "sales")
    await page.goto("/ai")
    await page.getByRole("button", { name: "历史记录" }).click()
    const panel = page.getByRole("navigation", { name: "会话记录" })
    const row = panel.getByRole("link", { name: /公司一年有几天年假/ }).first()
    await expect(row).toContainText(/\d{2}:\d{2}/)

    await row.hover()
    await panel
      .getByRole("button", { name: /更多操作：公司一年有几天年假/ })
      .first()
      .click()
    await page.getByRole("menuitem", { name: "重命名" }).click()
    const name = uniq("年假问答")
    await panel.getByRole("textbox", { name: "会话名称" }).fill(name)
    await page.keyboard.press("Enter")
    const renamed = panel.getByRole("link", { name: new RegExp(name) })
    await expect(renamed).toBeVisible()

    await renamed.hover()
    await panel.getByRole("button", { name: `更多操作：${name}` }).click()
    await page.getByRole("menuitem", { name: "删除" }).click()
    await page.getByRole("alertdialog", { name: "删除会话" }).getByRole("button", { name: "确认删除" }).click()
    await expect(renamed).toHaveCount(0)
  })

  test("有进行中商机的客户：退回公海弹窗直接说明原因，不能确认（不改演示数据）", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/customers")
    await page.getByRole("link").filter({ hasText: "深圳明理律师事务所" }).first().click()
    await page.getByRole("button", { name: "退回公海" }).click()
    const dialog = page.getByRole("dialog", { name: "退回公海" })
    await expect(dialog).toContainText(/还有 \d+ 个进行中的商机，不能退回/)
    await dialog.getByRole("button", { name: "长期联系不上" }).click()
    await expect(dialog.getByRole("button", { name: "确认退回" })).toBeDisabled()
    await dialog.getByRole("button", { name: "取消" }).click()
  })

  test("口径与命名：本月成交、进行中金额、我的报价单、报价负责人、审批建议", async ({ page }) => {
    await loginAs(page, "sales")
    await page.goto("/dashboard")
    await expect(page.getByText("本月成交", { exact: true })).toBeVisible()
    await expect(page.getByText("进行中金额")).toBeVisible()
    await page.goto("/quotes")
    await expect(page.getByRole("button", { name: /我的报价单/ })).toBeVisible()
    await expect(page.getByRole("columnheader", { name: "负责人" })).toBeVisible()
    await loginAs(page, "manager")
    await page.goto("/approvals")
    await expect(page.getByText(/审批建议：/).first()).toBeVisible()
    await expect(page.getByText(/AI 建议/)).toHaveCount(0)
  })
})
