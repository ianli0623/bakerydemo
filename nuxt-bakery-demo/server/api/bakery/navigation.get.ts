import type { BakeryNavigationItem } from '#shared/types/bakery';
import { defineEventHandler } from 'h3';
import { fetchBakery } from '../../utils/bakery.ts';
import { getBakeryLocale } from '../../utils/bakery-locale.ts';
import {
  toBakerySiteSettings,
  toNavigationItems,
} from '../../utils/bakery-settings.ts';

export default defineEventHandler(
  async (event): Promise<BakeryNavigationItem[]> => {
    const locale = getBakeryLocale(event);
    const settings = toBakerySiteSettings(
      await fetchBakery<unknown>(event, '/api/site-settings/', { locale }),
    );
    return toNavigationItems(settings);
  },
);
