import { isValidStandardPageSlug } from './bakery.ts';

export const BAKERY_LOCALES = ['zh-hant', 'en'] as const;
export type BakeryLocale = (typeof BAKERY_LOCALES)[number];
export const DEFAULT_BAKERY_LOCALE: BakeryLocale = 'en';

export function normalizeBakeryLocale(value: unknown): BakeryLocale {
  if (value === 'zh-tw') {
    return 'zh-hant';
  }

  if (value === 'zh-hant' || value === 'en') {
    return value;
  }

  throw new Error('Unsupported Bakery locale.');
}

export function localizedPagePath(locale: BakeryLocale, slug = ''): string {
  if (slug && !isValidStandardPageSlug(slug)) {
    throw new Error('Page slug is invalid.');
  }

  const prefix = locale === 'en' ? '/en' : '/zh-tw';
  return slug ? `${prefix}/${slug}/` : `${prefix}/`;
}
