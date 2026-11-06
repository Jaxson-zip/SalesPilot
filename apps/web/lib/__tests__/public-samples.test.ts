import { execFileSync } from "node:child_process"
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs"
import path from "node:path"

import { describe, expect, it } from "vitest"

// 回归：样例 PDF 曾被 .gitignore 的 `*.pdf` 规则挡住，本地有文件、仓库里没有，线上「下载样例」全部 404。
// 这里扫描页面里引用的 /samples/* 文件：必须存在，并且不能被 git 忽略（否则不会进仓库和线上镜像）。

const WEB_ROOT = path.resolve(__dirname, "../..")
const SOURCE_DIRS = ["app", "components", "lib"]

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name)
    if (name === "__tests__" || name === "node_modules") return []
    if (statSync(full).isDirectory()) return sourceFiles(full)
    return /\.(ts|tsx)$/.test(name) ? [full] : []
  })
}

function referencedSamples(): string[] {
  const found = new Set<string>()
  for (const dir of SOURCE_DIRS) {
    for (const file of sourceFiles(path.join(WEB_ROOT, dir))) {
      for (const m of readFileSync(file, "utf8").matchAll(/["'`](\/samples\/[^"'`]+)["'`]/g)) {
        found.add(m[1])
      }
    }
  }
  return [...found].sort()
}

function isGitIgnored(file: string): boolean {
  try {
    execFileSync("git", ["check-ignore", "-q", file], { cwd: WEB_ROOT, stdio: "ignore" })
    return true // 退出码 0：被忽略
  } catch {
    return false // 退出码 1：未被忽略（或不在 git 仓库里，此时无从判断，不算失败）
  }
}

describe("页面引用的样例文件", () => {
  const samples = referencedSamples()

  it("能扫描到样例引用", () => {
    expect(samples).toContain("/samples/invoice-sample.pdf")
  })

  it.each(samples)("%s 存在且会进仓库", (href) => {
    const file = path.join(WEB_ROOT, "public", href)
    expect(existsSync(file)).toBe(true)
    expect(isGitIgnored(file)).toBe(false)
  })
})
