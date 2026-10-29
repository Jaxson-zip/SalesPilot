import { describe, expect, it } from "vitest"

import { runQueue, sampleChipName, samplesBusy, samplesLabel, toSamplesIn, type SampleItem } from "@/lib/samples"

const item = (doc: string): SampleItem => ({ name: "a.png", doc_type: doc, fields: [], quality: "clear" })

describe("客户样例图片", () => {
  it("标签：识别中显示进度，完成后显示张数、类数和失败数", () => {
    const busy = { total: 30, done: 12, items: [item("发票")], failed: [] }
    expect(samplesLabel(busy)).toBe("识别中 12/30")
    expect(samplesBusy(busy)).toBe(true)
    const done = { total: 3, done: 3, items: [item("发票"), item("提单")], failed: [new File([], "x.png")] }
    expect(samplesLabel(done)).toBe("3 张 · 2 类单据，1 张失败")
    expect(sampleChipName({ total: 3, items: done.items })).toBe("客户样例图片（3 张 · 2 类单据）")
  })

  it("全部识别完且至少成功一张才能发送；只发成功的", () => {
    expect(toSamplesIn({ total: 2, done: 1, items: [item("发票")], failed: [] })).toBeNull()
    expect(toSamplesIn({ total: 1, done: 1, items: [], failed: [new File([], "x.png")] })).toBeNull()
    expect(toSamplesIn({ total: 2, done: 2, items: [item("发票")], failed: [new File([], "x.png")] })).toEqual({
      total: 2,
      items: [item("发票")],
    })
  })

  it("并发不超过上限，失败的单独回调，不中断其他任务", async () => {
    let running = 0
    let peak = 0
    const settled: (number | string)[] = []
    await runQueue(
      [1, 2, 3, 4, 5, 6, 7],
      async (n) => {
        running++
        peak = Math.max(peak, running)
        await new Promise((r) => setTimeout(r, 5))
        running--
        if (n === 4) throw new Error("坏图")
        return n * 10
      },
      3,
      (_n, r) => settled.push(r instanceof Error ? r.message : r),
    )
    expect(peak).toBe(3)
    expect(settled).toHaveLength(7)
    expect(settled).toContain("坏图")
    expect(settled).toContain(70)
  })
})
