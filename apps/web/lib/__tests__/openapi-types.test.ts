/**
 * types/generated/openapi.d.ts 必须与 docs/api/openapi.yaml 一致：
 * 后端接口变了（core 的测试会要求重新导出 yaml），前端没重新生成时这个测试失败。
 */
import { readFileSync } from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"

import openapiTS, { astToString } from "openapi-typescript"
import prettier from "prettier"
import { expect, test } from "vitest"

const WEB = path.resolve(__dirname, "../..")
const SPEC = path.resolve(WEB, "../../docs/api/openapi.yaml")
const OUT = path.resolve(WEB, "types/generated/openapi.d.ts")

test("生成的接口类型是最新的（不是请运行 pnpm gen:api）", async () => {
  const ast = await openapiTS(pathToFileURL(SPEC), { defaultNonNullable: false })
  const options = (await prettier.resolveConfig(OUT)) ?? {}
  const expected = await prettier.format(astToString(ast), { ...options, filepath: OUT })
  // CLI 生成的文件开头多一段「自动生成，请勿手改」的注释，比较时去掉
  const actual = readFileSync(OUT, "utf-8").replace(/^\/\*\*[\s\S]*?\*\/\s*/, "")
  expect(actual).toBe(expected)
}, 30_000)
