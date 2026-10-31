import { describe, expect, it } from "vitest"

import { joinSpeech, recognitionCtor, speechErrorText, transcriptOf, type SpeechResultEventLike } from "@/lib/speech"

function event(parts: string[]): SpeechResultEventLike {
  const results = parts.map((t, i) => Object.assign([{ transcript: t }], { isFinal: i < parts.length - 1 }))
  return { results: Object.assign(results, { length: results.length }) }
}

describe("语音输入", () => {
  it("没有识别接口就不支持", () => {
    expect(recognitionCtor(undefined)).toBeNull()
    expect(recognitionCtor({})).toBeNull()
    class Fake {}
    expect(recognitionCtor({ webkitSpeechRecognition: Fake })).toBe(Fake)
    expect(recognitionCtor({ SpeechRecognition: Fake })).toBe(Fake)
  })

  it("把所有片段拼起来（含临时结果）", () => {
    expect(transcriptOf(event(["今天拜访了王总", "他说预算批了"]))).toBe("今天拜访了王总他说预算批了")
    expect(transcriptOf(event([]))).toBe("")
  })

  it("接在已有内容后面，缺标点补逗号", () => {
    expect(joinSpeech("", "预算批了")).toBe("预算批了")
    expect(joinSpeech("王总说", "预算批了")).toBe("王总说，预算批了")
    expect(joinSpeech("王总说。", "预算批了")).toBe("王总说。预算批了")
    expect(joinSpeech("第一行\n", "第二行")).toBe("第一行\n第二行")
    expect(joinSpeech("已有内容", "")).toBe("已有内容")
  })

  it("出错提示：自己停下不提示，国内 Chrome 的 network 错误给替代办法", () => {
    expect(speechErrorText("aborted")).toBeNull()
    expect(speechErrorText("network")).toContain("Edge")
    expect(speechErrorText("not-allowed")).toContain("麦克风权限")
    expect(speechErrorText("weird")).toContain("weird")
  })
})
