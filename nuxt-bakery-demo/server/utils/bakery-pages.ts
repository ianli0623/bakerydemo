import type {
  BakeryFeaturedSection,
  BakeryHomePage,
  BakeryHomeViewModel,
  BakeryPageList,
  BakeryPageSummary,
} from '../../shared/types/bakery.ts';
import { isValidStandardPageSlug } from '../../shared/utils/bakery.ts';
import {
  localizedPagePath,
  type BakeryLocale,
} from '../../shared/utils/locale.ts';

export async function collectPaginatedItems<T>(
  fetchPage: (offset: number) => Promise<BakeryPageList<T>>,
): Promise<T[]> {
  const items: T[] = [];
  let totalCount = Number.POSITIVE_INFINITY;

  while (items.length < totalCount) {
    const response = await fetchPage(items.length);
    totalCount = response.meta.total_count;

    if (response.items.length === 0) {
      break;
    }

    items.push(...response.items);
  }

  return items;
}

export function getFeaturedPageIds(home: BakeryHomePage): number[] {
  return [
    home.featured_section_1?.id,
    home.featured_section_2?.id,
    home.featured_section_3?.id,
  ].filter(
    (id, index, ids): id is number =>
      typeof id === 'number' && ids.indexOf(id) === index,
  );
}

export function getHomeReferenceIds(home: BakeryHomePage): number[] {
  return [
    home.hero_cta_link?.id,
    home.secondary_hero_cta_link?.id,
    ...getFeaturedPageIds(home),
  ].filter(
    (id, index, ids): id is number =>
      typeof id === 'number' && ids.indexOf(id) === index,
  );
}

export function createStandardPageQuery(
  slug: string,
  homePageId: number,
  locale: BakeryLocale,
): Record<string, string> {
  return {
    type: 'base.StandardPage',
    child_of: String(homePageId),
    locale,
    slug: validateSlug(slug),
    fields: '*',
    limit: '1',
  };
}

export function validateSlug(value: string | undefined): string {
  const slug = value?.trim() ?? '';

  if (!isValidStandardPageSlug(slug)) {
    throw new Error('頁面 slug 不正確。');
  }

  return slug;
}

export function toNuxtPagePath(
  reference: BakeryPageSummary | null,
  locale: BakeryLocale,
): string | null {
  const slug = reference?.meta.slug;
  if (!isValidStandardPageSlug(slug)) {
    return null;
  }

  return localizedPagePath(locale, slug);
}

export function enrichHomePage(
  home: BakeryHomePage,
  topLevelPages: BakeryPageSummary[],
  locale: BakeryLocale,
): BakeryHomeViewModel {
  const pageById = new Map(topLevelPages.map((page) => [page.id, page]));
  const heroCtaReference = home.hero_cta_link;
  const heroCtaPage = heroCtaReference
    ? (pageById.get(heroCtaReference.id) ?? heroCtaReference)
    : null;
  const references = [
    [home.featured_section_1, home.featured_section_1_title],
    [home.featured_section_2, home.featured_section_2_title],
    [home.featured_section_3, home.featured_section_3_title],
  ] as const;

  const featuredSections = references.flatMap<BakeryFeaturedSection>(
    ([reference, configuredTitle]) => {
      if (!reference) {
        return [];
      }

      const page = pageById.get(reference.id);
      const path = toNuxtPagePath(page ?? null, locale);
      if (!path) {
        return [];
      }

      return [
        {
          id: reference.id,
          title: configuredTitle || reference.title,
          url: path,
        },
      ];
    },
  );

  return {
    ...home,
    featuredSections,
    heroCtaPath: toNuxtPagePath(heroCtaPage, locale),
    secondaryHeroCtaPath: (() => {
      const reference = home.secondary_hero_cta_link;
      const page = reference ? (pageById.get(reference.id) ?? reference) : null;
      const path = toNuxtPagePath(page, locale);
      return path && home.secondary_hero_cta_fragment
        ? `${path}#${home.secondary_hero_cta_fragment}`
        : path;
    })(),
  };
}

export function firstPage<T>(items: T[]): T | undefined {
  return items[0];
}
