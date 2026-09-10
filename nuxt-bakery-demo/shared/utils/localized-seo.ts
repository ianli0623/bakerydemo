import {
  localizedPagePath,
  type BakeryLocale
} from './locale.ts'

interface PageSeoSource {
  title: string
  seoTitle: string
  searchDescription: string
  introduction: string
}

interface HreflangAlternative {
  hreflang: 'zh-Hant' | 'en' | 'x-default'
  href: string
}

export function getLocalizedSeoLinks(
  origin: string,
  locale: BakeryLocale,
  slug = ''
): { canonical: string; alternatives: HreflangAlternative[] } {
  const toAbsoluteUrl = (path: string) => new URL(path, origin).toString()
  const chineseUrl = toAbsoluteUrl(localizedPagePath('zh-hant', slug))
  const englishUrl = toAbsoluteUrl(localizedPagePath('en', slug))

  return {
    canonical: locale === 'en' ? englishUrl : chineseUrl,
    alternatives: [
      { hreflang: 'zh-Hant', href: chineseUrl },
      { hreflang: 'en', href: englishUrl },
      { hreflang: 'x-default', href: englishUrl }
    ]
  }
}

export function getPageSeoPresentation(
  page: PageSeoSource,
  titleSuffix: string
): { title: string; description: string } {
  const title = page.seoTitle.trim()
    || [page.title.trim(), titleSuffix.trim()].filter(Boolean).join(' | ')

  return {
    title,
    description: page.searchDescription.trim() || page.introduction.trim()
  }
}
