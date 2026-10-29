import { api } from "@/lib/api"

/**
 * 客户样例图片（出方案用）：POST /api/agent/samples 一次识别一张，返回单据类型、字段名、清晰度。
 * 前端限量并发上传、显示进度，发送时把成功的结果带给 /chat，由后端汇总后走出方案流程。原图不入库。
 */
export interface SampleItem {
  name: string
  doc_type: string
  fields: string[]
  quality: "clear" | "blurry" | "handwritten"
}

export interface SamplesIn {
  total: number
  items: SampleItem[]
}

/** 上传中的样例：total 张，已完成 done 张（成功的在 items，失败的文件在 failed，可重试） */
export interface SampleState {
  total: number
  done: number
  items: SampleItem[]
  failed: File[]
}

export const SAMPLE_ACCEPT = ".png,.jpg,.jpeg,.webp"
export const MAX_SAMPLES = 30
export const SAMPLE_CONCURRENCY = 3
export const SAMPLE_DEFAULT_ASK = "按这些客户样例图片出方案：识别单据类型和字段，拆解需求"

export function analyzeSample(file: File): Promise<SampleItem> {
  const form = new FormData()
  form.append("file", file)
  return api.upload<SampleItem>("/api/agent/samples", form)
}

export const sampleTypeCount = (items: SampleItem[]) => new Set(items.map((i) => i.doc_type)).size

/** 用户气泡上的标签，与后端历史记录里的名称一致 */
export const sampleChipName = (s: SamplesIn) => `客户样例图片（${s.total} 张 · ${sampleTypeCount(s.items)} 类单据）`

export const samplesBusy = (s: SampleState | null) => Boolean(s && s.done < s.total)

/** 输入框上方的标签文字 */
export function samplesLabel(s: SampleState): string {
  if (s.done < s.total) return `识别中 ${s.done}/${s.total}`
  const failed = s.failed.length ? `，${s.failed.length} 张失败` : ""
  return `${s.total} 张 · ${sampleTypeCount(s.items)} 类单据${failed}`
}

/** 能发送：全部识别完且至少成功一张 */
export function toSamplesIn(s: SampleState | null): SamplesIn | null {
  if (!s || s.done < s.total || s.items.length === 0) return null
  return { total: s.total, items: s.items }
}

/** 限量并发执行：每个任务结束（成功或失败）都回调一次，用来更新进度 */
export async function runQueue<T, R>(
  inputs: T[],
  worker: (input: T) => Promise<R>,
  limit: number,
  onSettled: (input: T, result: R | Error) => void,
): Promise<void> {
  let next = 0
  const lane = async () => {
    while (next < inputs.length) {
      const input = inputs[next++]
      try {
        onSettled(input, await worker(input))
      } catch (err) {
        onSettled(input, err instanceof Error ? err : new Error(String(err)))
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, inputs.length) }, lane))
}
