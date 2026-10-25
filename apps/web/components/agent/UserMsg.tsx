/** 用户消息：右侧灰色气泡 */
export function UserMsg({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-2xl bg-zinc-100 px-4 py-2.5 text-[14px] leading-6 break-words whitespace-pre-wrap">
        {text}
      </div>
    </div>
  )
}
