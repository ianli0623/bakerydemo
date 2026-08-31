import type {
  BakeryContentLink,
  BakeryImage,
  BakeryRendition,
  BakeryStreamBlock
} from '../../shared/types/bakery.ts'

export function getHeadingTag(size: string): 'h2' | 'h3' | 'h4' {
  return size === 'h3' || size === 'h4' ? size : 'h2'
}

export function getCardHeadingTag(sectionHeading: string): 'h2' | 'h3' {
  return sectionHeading.trim() ? 'h3' : 'h2'
}

export function getImageRendition(
  block: BakeryStreamBlock
): BakeryRendition | null {
  return block.type === 'image_block'
    ? block.value.image.meta.rendition ?? null
    : null
}

export function getRenditionSource(rendition: BakeryRendition): string {
  return rendition.full_url || rendition.url
}

export interface ImagePresentation {
  src: string
  width: number
  height: number
  alt: string
}

export function getImagePresentation(
  image: BakeryImage,
  fallbackAlt: string
): ImagePresentation | null {
  const rendition = image.meta.rendition
  if (!rendition) {
    return null
  }

  return {
    src: getRenditionSource(rendition),
    width: rendition.width,
    height: rendition.height,
    alt: rendition.alt.trim() || fallbackAlt.trim() || image.title
  }
}

export type LinkPresentation =
  | { kind: 'internal'; to: string; label: string }
  | { kind: 'external'; href: string; label: string; newTab: boolean }
  | { kind: 'disabled'; label: string; status: '即將提供' }

function disabledLink(label: string): LinkPresentation {
  return { kind: 'disabled', label, status: '即將提供' }
}

function isSafeInternalHref(href: string): boolean {
  if (!href.startsWith('/') || href.startsWith('//') || href.includes('\\')) {
    return false
  }

  try {
    return new URL(href, 'http://bakery.local').origin === 'http://bakery.local'
  } catch {
    return false
  }
}

function isSafeExternalHref(href: string): boolean {
  try {
    return ['http:', 'https:', 'mailto:', 'tel:'].includes(
      new URL(href).protocol
    )
  } catch {
    return false
  }
}

export function getLinkPresentation(
  link: BakeryContentLink
): LinkPresentation {
  const href = link.href?.trim() ?? ''

  if (link.kind === 'internal' && isSafeInternalHref(href)) {
    return { kind: 'internal', to: href, label: link.label }
  }

  if (link.kind === 'external' && isSafeExternalHref(href)) {
    return {
      kind: 'external',
      href,
      label: link.label,
      newTab: link.new_tab
    }
  }

  return disabledLink(link.label)
}

interface StructuredBlockIdentity {
  id: string
  type: string
  value?: unknown
}

function getBlockHeading(block: StructuredBlockIdentity): string | undefined {
  if (!block.value || typeof block.value !== 'object' || !('heading' in block.value)) {
    return undefined
  }

  return typeof block.value.heading === 'string' ? block.value.heading.trim() : undefined
}

const structuredBlockAnchors: Record<string, string> = {
  process_steps: 'vendor-process',
  case_study: 'case-studies'
}

export function getStructuredBlockAnchor(
  block: StructuredBlockIdentity,
  blocks: StructuredBlockIdentity[],
  reservedAnchors: string[] = []
): string | undefined {
  if (
    block.type === 'card_grid'
    && getBlockHeading(block) === '驗證機構與合規名單'
  ) {
    if (reservedAnchors.includes('certified-list')) {
      return undefined
    }

    const firstCertifiedList = blocks.find(candidate =>
      candidate.type === 'card_grid'
      && getBlockHeading(candidate) === '驗證機構與合規名單'
    )
    return firstCertifiedList?.id === block.id ? 'certified-list' : undefined
  }

  const anchor = structuredBlockAnchors[block.type]
  if (!anchor || reservedAnchors.includes(anchor)) {
    return undefined
  }

  return blocks.find(candidate => candidate.type === block.type)?.id ===
    block.id
    ? anchor
    : undefined
}

export function getDocumentRowAnchor(number: string): string | undefined {
  const normalized = number.trim()
  return /^\d+$/.test(normalized) ? `doc-${normalized}` : undefined
}

export type EmbedPresentation =
  | { kind: 'iframe'; url: string }
  | { kind: 'link'; url: string }

export function getEmbedPresentation(
  value: string
): EmbedPresentation | null {
  let url: URL

  try {
    url = new URL(value)
  } catch {
    return null
  }

  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    return null
  }

  const hostname = url.hostname.toLowerCase()
  let videoId: string | null = null

  if (hostname === 'youtu.be') {
    videoId = url.pathname.split('/').filter(Boolean)[0] ?? null
  } else if (
    hostname === 'youtube.com' ||
    hostname === 'www.youtube.com' ||
    hostname === 'm.youtube.com' ||
    hostname === 'youtube-nocookie.com' ||
    hostname === 'www.youtube-nocookie.com'
  ) {
    videoId = url.pathname.startsWith('/embed/')
      ? url.pathname.split('/')[2] ?? null
      : url.searchParams.get('v')
  }

  if (videoId && /^[a-zA-Z0-9_-]{6,}$/.test(videoId)) {
    return {
      kind: 'iframe',
      url: `https://www.youtube-nocookie.com/embed/${videoId}`
    }
  }

  if (
    hostname === 'vimeo.com' ||
    hostname === 'www.vimeo.com' ||
    hostname === 'player.vimeo.com'
  ) {
    const vimeoId = url.pathname.split('/').filter(Boolean).at(-1)
    if (vimeoId && /^\d+$/.test(vimeoId)) {
      return {
        kind: 'iframe',
        url: `https://player.vimeo.com/video/${vimeoId}`
      }
    }
  }

  return { kind: 'link', url: url.toString() }
}
