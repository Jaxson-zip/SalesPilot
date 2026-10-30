import { defineConfig, devices } from "@playwright/test"

/**
 * 浏览器自动化测试：对运行中的 docker compose 环境（http://127.0.0.1:3000）做真实点击和拖拽。
 * 运行前：docker compose up -d && docker compose exec core python -m seed
 * 运行：  pnpm test:e2e        （有界面调试：pnpm test:e2e --headed）
 * 每个用例通过接口新建自己的数据，不依赖、也不修改演示数据；跑完可用 `python -m seed --reset` 清理。
 */
export default defineConfig({
  testDir: "./e2e",
  // 企业微信推送开着时拒绝运行（测试数据会被推送到真实的群）
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000",
    viewport: { width: 1440, height: 900 },
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        // 可用本机已安装的浏览器，免下载：PW_CHANNEL=msedge（Windows 自带）或 chrome
        channel: process.env.PW_CHANNEL || undefined,
      },
    },
  ],
})
