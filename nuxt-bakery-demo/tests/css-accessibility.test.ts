import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const css = readFileSync(
  new URL('../app/assets/css/main.css', import.meta.url),
  'utf8'
)

function getCustomProperty(name: string): string {
  const match = css.match(new RegExp(`${name}:\\s*(#[0-9a-f]{3}(?:[0-9a-f]{3})?)`, 'i'))

  assert.ok(match, `${name} must be defined as a hex color`)

  return match[1].length === 4
    ? `#${[...match[1].slice(1)].map((digit) => digit.repeat(2)).join('')}`
    : match[1]
}

function relativeLuminance(hex: string): number {
  const channels = hex
    .slice(1)
    .match(/.{2}/g)
    ?.map((channel) => Number.parseInt(channel, 16) / 255)

  assert.ok(channels)

  const [red, green, blue] = channels.map((channel) =>
    channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4
  )

  return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)
}

function contrastRatio(foreground: string, background: string): number {
  const foregroundLuminance = relativeLuminance(foreground)
  const backgroundLuminance = relativeLuminance(background)
  const lighter = Math.max(foregroundLuminance, backgroundLuminance)
  const darker = Math.min(foregroundLuminance, backgroundLuminance)

  return (lighter + 0.05) / (darker + 0.05)
}

test('muted small text meets WCAG AA on every light site surface', () => {
  const muted = getCustomProperty('--color-muted')
  const lightSurfaces = [
    '--color-surface',
    '--color-sky',
    '--color-page',
    '--color-mint'
  ]

  for (const surface of lightSurfaces) {
    const ratio = contrastRatio(muted, getCustomProperty(surface))

    assert.ok(
      ratio >= 4.5,
      `${muted} on ${surface} has contrast ${ratio.toFixed(2)}:1; expected at least 4.5:1`
    )
  }
})
