// 把 HTML 制度文档打印成 PDF（带页眉页码，用来验证 PDF 加载时的页眉页脚清洗）。
// 运行（在 apps/web 下，借用其中的 Playwright）：node ../../services/core/seed/knowledge/sources/build_pdf.mjs
import { createRequire } from "node:module"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(path.join(process.cwd(), "package.json"))
const { chromium } = require("@playwright/test")

const src = path.join(here, "合同审批与回款流程.html")
const out = path.join(here, "..", "company", "合同审批与回款流程.pdf")

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || "msedge" })
const page = await browser.newPage()
await page.goto(pathToFileURL(src).href)
await page.pdf({
  path: out,
  format: "A4",
  margin: { top: "22mm", bottom: "20mm", left: "18mm", right: "18mm" },
  displayHeaderFooter: true,
  headerTemplate: '<div style="font-size:9px;width:100%;text-align:right;padding-right:18mm;color:#888">SalesPilot 演示公司 内部制度</div>',
  footerTemplate: '<div style="font-size:9px;width:100%;text-align:center;color:#888">第 <span class="pageNumber"></span> 页</div>',
})
await browser.close()
console.log(out)
