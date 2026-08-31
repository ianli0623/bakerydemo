export function normalizeBaseUrl(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) {
    throw new Error('尚未設定 NUXT_BAKERY_BASE_URL。')
  }

  const url = new URL(trimmed)
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error('Bakery Base URL 必須使用 HTTP 或 HTTPS。')
  }

  return url.toString().replace(/\/+$/, '')
}

export function resolveMediaUrl(
  baseUrl: string,
  value: string | null | undefined
): string | null {
  if (!value) {
    return null
  }

  if (/^https?:\/\//i.test(value)) {
    return value
  }

  return new URL(value, `${normalizeBaseUrl(baseUrl)}/`).toString()
}

export function resolvePayloadMediaUrls(
  value: unknown,
  baseUrl: string
): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => resolvePayloadMediaUrls(item, baseUrl))
  }

  if (typeof value !== 'object' || value === null) {
    return value
  }

  const source = value as Record<string, unknown>
  const normalized = Object.fromEntries(
    Object.entries(source).map(([key, item]) => [
      key,
      resolvePayloadMediaUrls(item, baseUrl)
    ])
  )

  const renditionUrl = normalized.url
  const isRendition =
    typeof renditionUrl === 'string' &&
    typeof normalized.width === 'number' &&
    typeof normalized.height === 'number'

  if (isRendition) {
    normalized.full_url = resolveMediaUrl(baseUrl, renditionUrl)
  }

  return normalized
}

export function getUpstreamStatus(error: unknown): number | undefined {
  if (typeof error !== 'object' || error === null) {
    return undefined
  }

  const value = error as {
    response?: { status?: number }
    statusCode?: number
    status?: number
  }

  return value.response?.status ?? value.statusCode ?? value.status
}

export interface BakeryErrorDetails {
  statusCode: number
  statusMessage: string
}

export function toBakeryErrorDetails(error: unknown): BakeryErrorDetails {
  const status = getUpstreamStatus(error)

  if (status === 400) {
    return {
      statusCode: 400,
      statusMessage: 'Bakery API 查詢參數不正確。'
    }
  }

  if (status === 404) {
    return {
      statusCode: 404,
      statusMessage: '找不到指定的已發布頁面。'
    }
  }

  return {
    statusCode: 502,
    statusMessage: '目前無法連線到 Bakery CMS。'
  }
}
