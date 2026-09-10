import type {
  BakeryHomePage,
  BakeryHomeViewModel,
  BakeryPageSummary,
} from '#shared/types/bakery';
import { defineEventHandler } from 'h3';
import { fetchBakery } from '../../utils/bakery.ts';
import { getUpstreamStatus } from '../../utils/bakery-core.ts';
import { getBakeryLocale } from '../../utils/bakery-locale.ts';
import {
  enrichHomePage,
  getHomeReferenceIds,
} from '../../utils/bakery-pages.ts';
import { toBakerySiteSettings } from '../../utils/bakery-settings.ts';

export default defineEventHandler(
  async (event): Promise<BakeryHomeViewModel> => {
    const locale = getBakeryLocale(event);
    const settings = toBakerySiteSettings(
      await fetchBakery<unknown>(event, '/api/site-settings/', { locale }),
    );
    const home = await fetchBakery<BakeryHomePage>(
      event,
      `/api/v2/pages/${settings.home_page_id}/`,
      { fields: '*' },
    );

    const featuredPages = await Promise.all(
      getHomeReferenceIds(home).map(async (id) => {
        try {
          return await fetchBakery<BakeryPageSummary>(
            event,
            `/api/v2/pages/${id}/`,
          );
        } catch (error) {
          if (getUpstreamStatus(error) === 404) {
            return null;
          }

          throw error;
        }
      }),
    );

    return enrichHomePage(
      home,
      featuredPages.filter((page): page is BakeryPageSummary => page !== null),
      locale,
    );
  },
);
