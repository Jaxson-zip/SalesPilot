/** 只放行 http / https 外链和站内路径（/ 开头、不是 //）：javascript:、data: 等一律不渲染成链接 */
export function safeHref(url: string | null | undefined): string | null {
  if (!url) return null
  const v = url.trim()
  if (v.startsWith("/") && !v.startsWith("//")) return v
  try {
    const u = new URL(v)
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null
  } catch {
    return null
  }
}

/** 网站地址是否合法（和后端一致：http / https，只写域名的后端会补 https://） */
export function isWebsite(text: string): boolean {
  const v = text.trim()
  if (/^[\w-]+(\.[\w-]+)+(:\d+)?([/?#]\S*)?$/.test(v)) return true
  return /^https?:\/\//i.test(v) && safeHref(v) !== null && !/\s/.test(v)
}
