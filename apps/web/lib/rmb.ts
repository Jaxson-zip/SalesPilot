/** 人民币金额大写（报价单打印用）：12345.67 元 → 壹万贰仟叁佰肆拾伍元陆角柒分 */

const DIGITS = "零壹贰叁肆伍陆柒捌玖"
const UNITS = ["", "拾", "佰", "仟"]
const BIG = ["", "万", "亿", "万亿"]

/** 1–9999 的一节，内部的连续 0 读一个「零」，末尾的 0 不读 */
function groupUpper(g: number): string {
  let s = ""
  let pendingZero = false
  for (let i = 3; i >= 0; i--) {
    const d = Math.floor(g / 10 ** i) % 10
    if (d === 0) {
      if (s) pendingZero = true
      continue
    }
    if (pendingZero) s += "零"
    pendingZero = false
    s += DIGITS[d] + UNITS[i]
  }
  return s
}

function integerUpper(yuan: number): string {
  const groups: number[] = []
  for (let n = yuan; n > 0; n = Math.floor(n / 10000)) groups.push(n % 10000)
  let s = ""
  let pendingZero = false
  for (let gi = groups.length - 1; gi >= 0; gi--) {
    const g = groups[gi]
    if (g === 0) {
      if (s) pendingZero = true
      continue
    }
    // 上一节已有内容、且中间隔了 0（整节为 0 或本节不足千位）时补「零」
    if (s && (pendingZero || g < 1000)) s += "零"
    pendingZero = false
    s += groupUpper(g) + BIG[gi]
  }
  return s
}

/** 分 → 大写金额；负数或非整数返回空串 */
export function fenToRmbUpper(fen: number): string {
  if (!Number.isSafeInteger(fen) || fen < 0) return ""
  if (fen === 0) return "零元整"
  const yuan = Math.floor(fen / 100)
  const jiao = Math.floor((fen % 100) / 10)
  const cent = fen % 10
  let s = yuan > 0 ? `${integerUpper(yuan)}元` : ""
  if (jiao === 0 && cent === 0) return `${s}整`
  if (jiao > 0) s += `${DIGITS[jiao]}角`
  else if (yuan > 0) s += "零"
  if (cent > 0) s += `${DIGITS[cent]}分`
  return s
}
