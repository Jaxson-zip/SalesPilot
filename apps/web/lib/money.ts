/** 表单金额（元，字符串）↔ 分（整数）。不用浮点乘法，避免 0.1 + 0.2 之类的误差 */

const YUAN_RE = /^\d+(\.\d{0,2})?$/

/** "860" → 86000；"1,234.5" → 123450；非法或空 → null */
export function yuanToFen(input: string): number | null {
  const s = input.replace(/[,，\s¥]/g, "")
  if (!s || !YUAN_RE.test(s)) return null
  const [int, frac = ""] = s.split(".")
  const fen = Number(int) * 100 + Number(frac.padEnd(2, "0"))
  return Number.isSafeInteger(fen) ? fen : null
}

/** 86000 → "860"；123450 → "1234.50"（用于输入框回填，不带千分位） */
export function fenToYuanInput(fen: number): string {
  const yuan = Math.trunc(fen / 100)
  const cents = Math.abs(fen % 100)
  return cents === 0 ? String(yuan) : `${yuan}.${String(cents).padStart(2, "0")}`
}

/** 正整数（人数、赢率等）；非法 → null */
export function parsePositiveInt(input: string, { min = 1, max = Number.MAX_SAFE_INTEGER } = {}): number | null {
  const s = input.trim()
  if (!/^\d+$/.test(s)) return null
  const n = Number(s)
  return n >= min && n <= max ? n : null
}

/**
 * 整单折后价（分），与 core app.rules.calculators.discounted_price 同一口径：
 * 折扣率按万分之一取整，折扣额 = 原价 × 折扣率，按分四舍五入（半分进位），折后价 = 原价 − 折扣额。
 * 全程整数：原价拆成 万位 × 10000 + 余数，乘积不会超过安全整数。
 */
export function discountedPrice(listPrice: number, discountRate: number): number {
  const bp = Math.round(discountRate * 10000)
  if (listPrice <= 0 || bp <= 0) return listPrice
  const high = Math.floor(listPrice / 10000)
  const low = listPrice % 10000
  return listPrice - (high * bp + Math.floor((low * bp + 5000) / 10000))
}
