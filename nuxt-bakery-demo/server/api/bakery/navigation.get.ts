import type { BakeryNavigationItem } from '#shared/types/bakery'
import { defineEventHandler } from 'h3'
import { fetchBakery } from '../../utils/bakery.ts'
import {
  toBakerySiteSettings,
  toNavigationItems
} from '../../utils/bakery-settings.ts'

export default defineEventHandler(
  async (event): Promise<BakeryNavigationItem[]> => {
    const settings = toBakerySiteSettings(
      await fetchBakery<unknown>(event, '/api/site-settings/')
    )
    return toNavigationItems(settings)
  }
)
