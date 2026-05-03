export const CURRENCY_SYMBOL = 'BYN'

export interface PriceSettings {
  uah_rate: number
  try_rate: number
  uah_markup_500: number
  uah_markup_1000: number
  uah_markup_1500: number
  uah_markup_2000: number
  uah_markup_max: number
  try_markup_500: number
  try_markup_1000: number
  try_markup_1500: number
  try_markup_2000: number
  try_markup_max: number
}

export const DEFAULT_PRICE_SETTINGS: PriceSettings = {
  uah_rate: 0.069,
  try_rate: 0.07,
  uah_markup_500: 70,
  uah_markup_1000: 60,
  uah_markup_1500: 50,
  uah_markup_2000: 40,
  uah_markup_max: 30,
  try_markup_500: 70,
  try_markup_1000: 60,
  try_markup_1500: 50,
  try_markup_2000: 40,
  try_markup_max: 30,
}

export function toBYN(price: number, region: string, settings: PriceSettings = DEFAULT_PRICE_SETTINGS): number {
  if (price <= 0) return 0
  const isTR = region === 'TR'
  const rate = isTR ? settings.try_rate : settings.uah_rate
  let markupPct: number
  if (price <= 500)       markupPct = isTR ? settings.try_markup_500  : settings.uah_markup_500
  else if (price <= 1000) markupPct = isTR ? settings.try_markup_1000 : settings.uah_markup_1000
  else if (price <= 1500) markupPct = isTR ? settings.try_markup_1500 : settings.uah_markup_1500
  else if (price <= 2000) markupPct = isTR ? settings.try_markup_2000 : settings.uah_markup_2000
  else                    markupPct = isTR ? settings.try_markup_max  : settings.uah_markup_max
  return Math.ceil(price * rate * (1 + markupPct / 100))
}

export function formatBYN(byn: number): string {
  return byn.toLocaleString('ru-RU') + ' ' + CURRENCY_SYMBOL
}

export function getPrice(product: { price_byn?: number | null }): number | null {
  if (product.price_byn != null && product.price_byn > 0) return product.price_byn
  return null
}

export function priceLabel(product: { price_byn?: number | null }): string {
  const byn = product.price_byn
  if (byn == null || byn <= 0) return '—'
  return formatBYN(byn)
}
