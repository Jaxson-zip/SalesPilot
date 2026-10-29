import { describe, expect, it } from "vitest"

import { splitFollowUps } from "@/lib/agent-mode"

describe("splitFollowUps", () => {
  it("拆出「可以接着问」的追问建议，正文去掉这一段", () => {
    const text = "提成按毛利分档（出处：销售提成制度）\n\n可以接着问：\n- 低毛利合同怎么算？\n- 提成什么时候发？"
    expect(splitFollowUps(text)).toEqual({
      body: "提成按毛利分档（出处：销售提成制度）",
      questions: ["低毛利合同怎么算？", "提成什么时候发？"],
    })
  })

  it("兼容加粗、半角冒号和数字序号，最多 3 条", () => {
    const text = "正文\n**可以接着问:**\n1. 一\n2、二\n* 三\n- 四"
    expect(splitFollowUps(text).questions).toEqual(["一", "二", "三"])
  })

  it("没有追问段落时原样返回", () => {
    expect(splitFollowUps("知识库里没有找到这方面的资料")).toEqual({
      body: "知识库里没有找到这方面的资料",
      questions: [],
    })
  })
})
