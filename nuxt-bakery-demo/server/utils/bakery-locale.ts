import { createError, getQuery, type H3Event } from 'h3';
import {
  DEFAULT_BAKERY_LOCALE,
  normalizeBakeryLocale,
  type BakeryLocale,
} from '../../shared/utils/locale.ts';

export function getBakeryLocale(event: H3Event): BakeryLocale {
  const value = getQuery(event).locale ?? DEFAULT_BAKERY_LOCALE;

  try {
    return normalizeBakeryLocale(value);
  } catch {
    throw createError({
      statusCode: 400,
      message: '不支援指定的語系。',
    });
  }
}
