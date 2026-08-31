import { createError } from 'h3'
import type {
  BakeryImage,
  BakeryNavigationItem,
  BakeryRendition,
  BakerySiteSettings
} from '../../shared/types/bakery.ts'
import {
  localizedPagePath,
  normalizeBakeryLocale,
  type BakeryLocale
} from '../../shared/utils/locale.ts'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isString(value: unknown): value is string {
  return typeof value === 'string'
}

function isBakeryRendition(value: unknown): value is BakeryRendition {
  return (
    isRecord(value) &&
    isString(value.url) &&
    (value.full_url === undefined || isString(value.full_url)) &&
    typeof value.width === 'number' &&
    typeof value.height === 'number' &&
    isString(value.alt)
  )
}

function isBakeryImage(value: unknown): value is BakeryImage {
  return (
    isRecord(value) &&
    typeof value.id === 'number' &&
    isString(value.title) &&
    isRecord(value.meta) &&
    isString(value.meta.download_url) &&
    (value.meta.rendition === undefined ||
      isBakeryRendition(value.meta.rendition))
  )
}

function isLocalPath(value: unknown): value is string {
  if (
    !isString(value) ||
    !value.startsWith('/') ||
    value.startsWith('//') ||
    value.includes('\\')
  ) {
    return false
  }

  try {
    return new URL(value, 'http://bakery.local').origin === 'http://bakery.local'
  } catch {
    return false
  }
}

function isNavigationItem(
  value: unknown,
  locale: BakeryLocale
): value is BakeryNavigationItem {
  if (
    !isRecord(value) ||
    typeof value.id !== 'number' ||
    !Number.isInteger(value.id) ||
    !isString(value.title) ||
    !isString(value.slug) ||
    !isLocalPath(value.path)
  ) {
    return false
  }

  try {
    return value.path === localizedPagePath(locale, value.slug)
  } catch {
    return false
  }
}

function getPayloadLocale(input: Record<string, unknown>): BakeryLocale | null {
  try {
    return normalizeBakeryLocale(input.locale)
  } catch {
    return null
  }
}

function hasLocalizedHomePath(
  input: Record<string, unknown>,
  locale: BakeryLocale
): boolean {
  return (
    typeof input.home_page_id === 'number' &&
    Number.isInteger(input.home_page_id) &&
    input.home_page_id > 0 &&
    input.home_path === localizedPagePath(locale)
  )
}

export function isBakerySiteSettings(
  input: unknown
): input is BakerySiteSettings {
  if (!isRecord(input) || !isRecord(input.contact)) {
    return false
  }
  const locale = getPayloadLocale(input)
  if (!locale || !hasLocalizedHomePath(input, locale)) {
    return false
  }

  return (
    isString(input.brand_label) &&
    isString(input.title_suffix) &&
    isString(input.site_name) &&
    isString(input.site_tagline) &&
    isString(input.contact.heading) &&
    isString(input.contact.name) &&
    isString(input.contact.context) &&
    isString(input.contact.phone) &&
    isString(input.contact.phone_href) &&
    isString(input.contact.email) &&
    isString(input.footer_introduction) &&
    isString(input.organisation_text) &&
    (input.footer_logo === null || isBakeryImage(input.footer_logo)) &&
    Array.isArray(input.navigation) &&
    input.navigation.every((item) => isNavigationItem(item, locale))
  )
}

export function parseBakerySiteSettings(input: unknown): BakerySiteSettings {
  if (!isBakerySiteSettings(input)) {
    throw new Error('Bakery site settings payload is invalid.')
  }
  return input
}

export function toBakerySiteSettings(input: unknown): BakerySiteSettings {
  try {
    return parseBakerySiteSettings(input)
  } catch {
    throw createError({
      statusCode: 502,
      message: 'Bakery 網站設定格式錯誤。'
    })
  }
}

export function toNavigationItems(
  settings: BakerySiteSettings
): BakeryNavigationItem[] {
  return settings.navigation.map((item) => ({ ...item }))
}
