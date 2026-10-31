/**
 * 复制到剪贴板。navigator.clipboard 只在 https / localhost 下有（用局域网 IP 打开时是 undefined，
 * 直接调用会同步抛错，按钮看起来没反应），没有或被拒绝时退回到隐藏 textarea + execCommand。
 */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // 落到下面的旧办法
  }
  const el = document.createElement("textarea")
  el.value = text
  el.setAttribute("readonly", "")
  el.style.position = "fixed"
  el.style.opacity = "0"
  document.body.appendChild(el)
  el.select()
  try {
    return document.execCommand("copy")
  } catch {
    return false
  } finally {
    el.remove()
  }
}
