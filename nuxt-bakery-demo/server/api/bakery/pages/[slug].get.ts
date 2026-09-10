import type { BakeryPageList, BakeryStandardPage } from '#shared/types/bakery';
import { createError, defineEventHandler, getRouterParam } from 'h3';
import { fetchBakery } from '../../../utils/bakery.ts';
import { getBakeryLocale } from '../../../utils/bakery-locale.ts';
import {
  createStandardPageQuery,
  firstPage,
  validateSlug,
} from '../../../utils/bakery-pages.ts';
import { toBakerySiteSettings } from '../../../utils/bakery-settings.ts';

export default defineEventHandler(
  async (event): Promise<BakeryStandardPage> => {
    let slug: string;
    const locale = getBakeryLocale(event);

    try {
      slug = validateSlug(getRouterParam(event, 'slug'));
    } catch (error) {
      throw createError({
        statusCode: 400,
        message: error instanceof Error ? error.message : '頁面 slug 不正確。',
      });
    }

    const settings = toBakerySiteSettings(
      await fetchBakery<unknown>(event, '/api/site-settings/', { locale }),
    );
    const response = await fetchBakery<BakeryPageList<BakeryStandardPage>>(
      event,
      '/api/v2/pages/',
      createStandardPageQuery(slug, settings.home_page_id, locale),
    );
    const page = firstPage(response.items);

    if (!page) {
      throw createError({
        statusCode: 404,
        message: '找不到指定的已發布頁面。',
      });
    }

    return page;
  },
);
