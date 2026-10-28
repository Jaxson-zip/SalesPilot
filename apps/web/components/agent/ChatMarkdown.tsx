import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

/** 大模型常用表格列商机、报价明细：需要 GFM 才能渲染，否则整张表会被挤成一行 */
const REMARK_PLUGINS = [remarkGfm]
const MD_COMPONENTS: Components = {
  table: ({ children }) => (
    <div className="prose-table">
      <table>{children}</table>
    </div>
  ),
}

/** AI 正文的 Markdown 渲染（样式见 globals.css 的 .prose-chat） */
export function ChatMarkdown({ text }: { text: string }) {
  return (
    <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={MD_COMPONENTS}>
      {text}
    </ReactMarkdown>
  )
}
