export type FontScale = 'small' | 'default' | 'large'
export type FontScaleAction = 'decrease' | 'reset' | 'increase'

export const FONT_SCALE_STORAGE_KEY = 'semi-e187-font-scale'

interface ReadableStorage {
  getItem(key: string): string | null
}

interface WritableStorage {
  setItem(key: string, value: string): void
}

const fontScaleOrder: FontScale[] = ['small', 'default', 'large']

function isFontScale(value: unknown): value is FontScale {
  return fontScaleOrder.includes(value as FontScale)
}

export function reduceFontScale(
  current: FontScale,
  action: FontScaleAction
): FontScale {
  if (action === 'reset') {
    return 'default'
  }

  const offset = action === 'increase' ? 1 : -1
  const index = Math.min(
    fontScaleOrder.length - 1,
    Math.max(0, fontScaleOrder.indexOf(current) + offset)
  )
  return fontScaleOrder[index] ?? 'default'
}

export function readStoredFontScale(storage: ReadableStorage): FontScale {
  try {
    const value = storage.getItem(FONT_SCALE_STORAGE_KEY)
    return isFontScale(value) ? value : 'default'
  } catch {
    return 'default'
  }
}

export function writeStoredFontScale(
  storage: WritableStorage,
  value: FontScale
): void {
  try {
    storage.setItem(FONT_SCALE_STORAGE_KEY, value)
  } catch {
    // Storage can be unavailable in private browsing or restricted contexts.
  }
}
