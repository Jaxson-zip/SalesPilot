import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"

import { ChatMarkdown } from "@/components/agent/ChatMarkdown"

describe("ChatMarkdown", () => {
  it("渲染大模型回复里的表格（回归：没开 GFM 时整张表被挤成一行文字）", () => {
    const html = renderToStaticMarkup(
      <ChatMarkdown text={"| 商机 | 阶段 |\n|---|---|\n| 合同审查私有化 | 方案报价 |"} />,
    )
    expect(html).toContain('<div class="prose-table"><table>')
    expect(html).toContain("<th>商机</th>")
    expect(html).toContain("<td>方案报价</td>")
  })
})
