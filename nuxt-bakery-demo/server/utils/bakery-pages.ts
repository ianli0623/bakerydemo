import type {
  BakeryFeaturedSection,
  BakeryHomePage,
  BakeryHomeViewModel,
  BakeryPageList,
  BakeryPageSummary
} from '../../shared/types/bakery.ts'
import { isValidStandardPageSlug } from '../../shared/utils/bakery.ts'

export const BAKERY_HOME_PAGE_ID = 60

export async function collectPaginatedItems<T>(
  fetchPage: (offset: number) => Promise<BakeryPageList<T>>
): Promise<T[]> {
  const items: T[] = []
  let totalCount = Number.POSITIVE_INFINITY

  while (items.length < totalCount) {
    const response = await fetchPage(items.length)
    totalCount = response.meta.total_count

    if (response.items.length === 0) {
      break
    }

    items.push(...response.items)
  }

  return items
}

export function getFeaturedPageIds(home: BakeryHomePage): number[] {
  return [
    home.featured_section_1?.id,
    home.featured_section_2?.id,
    home.featured_section_3?.id
  ].filter(
    (id, index, ids): id is number =>
      typeof id === 'number' && ids.indexOf(id) === index
  )
}

export function getHomeReferenceIds(home: BakeryHomePage): number[] {
  return [home.hero_cta_link?.id, ...getFeaturedPageIds(home)].filter(
    (id, index, ids): id is number =>
      typeof id === 'number' && ids.indexOf(id) === index
  )
}

export function createStandardPageQuery(
  slug: string
): Record<string, string> {
  return {
    type: 'base.StandardPage',
    child_of: String(BAKERY_HOME_PAGE_ID),
    slug: validateSlug(slug),
    fields: '*',
    limit: '1'
  }
}

export function validateSlug(value: string | undefined): string {
  const slug = value?.trim() ?? ''

  if (!isValidStandardPageSlug(slug)) {
    throw new Error('頁面 slug 不正確。')
  }

  return slug
}

export function toNuxtPagePath(
  reference: BakeryPageSummary | null
): string | null {
  const htmlUrl = reference?.meta.html_url
  if (!htmlUrl) {
    return null
  }

  try {
    const url = new URL(htmlUrl, 'http://bakery.local')
    if (!['http:', 'https:'].includes(url.protocol)) {
      return null
    }
    return `${url.pathname}${url.search}${url.hash}`
  } catch {
    return null
  }
}

export function enrichHomePage(
  home: BakeryHomePage,
  topLevelPages: BakeryPageSummary[]
): BakeryHomeViewModel {
  const pageById = new Map(topLevelPages.map((page) => [page.id, page]))
  const heroCtaReference = home.hero_cta_link
  const heroCtaPage = heroCtaReference
    ? pageById.get(heroCtaReference.id) ?? heroCtaReference
    : null
  const references = [
    [home.featured_section_1, home.featured_section_1_title],
    [home.featured_section_2, home.featured_section_2_title],
    [home.featured_section_3, home.featured_section_3_title]
  ] as const

  const featuredSections = references.flatMap<BakeryFeaturedSection>(
    ([reference, configuredTitle]) => {
      if (!reference) {
        return []
      }

      const page = pageById.get(reference.id)
      if (!page?.meta.html_url) {
        return []
      }

      return [
        {
          id: reference.id,
          title: configuredTitle || reference.title,
          url: page.meta.html_url
        }
      ]
    }
  )

  return {
    ...home,
    featuredSections,
    heroCtaPath: toNuxtPagePath(heroCtaPage)
  }
}

export function firstPage<T>(items: T[]): T | undefined {
  return items[0]
}
