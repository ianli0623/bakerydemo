import type {
  BakeryHomePage,
  BakeryHomeViewModel,
  BakeryPageSummary
} from '#shared/types/bakery'
import { defineEventHandler } from 'h3'
import { fetchBakery } from '../../utils/bakery.ts'
import { getUpstreamStatus } from '../../utils/bakery-core.ts'
import {
  BAKERY_HOME_PAGE_ID,
  enrichHomePage,
  getHomeReferenceIds
} from '../../utils/bakery-pages.ts'

export default defineEventHandler(
  async (event): Promise<BakeryHomeViewModel> => {
    const home = await fetchBakery<BakeryHomePage>(
      event,
      `/api/v2/pages/${BAKERY_HOME_PAGE_ID}/`,
      { fields: '*' }
    )

    const featuredPages = await Promise.all(
      getHomeReferenceIds(home).map(async (id) => {
        try {
          return await fetchBakery<BakeryPageSummary>(
            event,
            `/api/v2/pages/${id}/`
          )
        } catch (error) {
          if (getUpstreamStatus(error) === 404) {
            return null
          }

          throw error
        }
      })
    )

    return enrichHomePage(
      home,
      featuredPages.filter((page): page is BakeryPageSummary => page !== null)
    )
  }
)
