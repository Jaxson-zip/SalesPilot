// 生成上传说明里的样例文件（带「样例」水印，虚构公司与税号）：
//   public/samples/invoice-sample.pdf / invoice-sample.png / receipt-sample.png
//   以及知识库样例（从 core 复制）：kb-sample.pdf / kb-sample.xlsx / kb-sample.md
// 运行（在 apps/web 下）：node scripts/samples/build.mjs
import { copyFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { chromium } from "@playwright/test"

const here = path.dirname(fileURLToPath(import.meta.url))
const out = path.resolve(here, "../../public/samples")
const core = path.resolve(here, "../../../../services/core")

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || "msedge" })
const page = await browser.newPage({ deviceScaleFactor: 2 })

await page.goto(pathToFileURL(path.join(here, "invoice.html")).href)
await page.pdf({ path: path.join(out, "invoice-sample.pdf"), width: "820px", height: "560px", printBackground: true })
await page.setViewportSize({ width: 820, height: 520 })
await page.locator(".sheet").screenshot({ path: path.join(out, "invoice-sample.png") })

await page.goto(pathToFileURL(path.join(here, "receipt.html")).href)
await page.setViewportSize({ width: 360, height: 700 })
await page.locator(".ticket").screenshot({ path: path.join(out, "receipt-sample.png") })
await browser.close()

copyFileSync(path.join(core, "seed/knowledge/company/合同审批与回款流程.pdf"), path.join(out, "kb-sample.pdf"))
copyFileSync(path.join(core, "app/packs/llm_deploy/knowledge/GPU与整机参数表.xlsx"), path.join(out, "kb-sample.xlsx"))
copyFileSync(path.join(core, "seed/knowledge/company/费用报销管理制度.md"), path.join(out, "kb-sample.md"))
console.log("samples written to", out)
