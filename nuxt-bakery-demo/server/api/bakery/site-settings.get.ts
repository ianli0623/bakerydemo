import type { BakerySiteSettings } from '#shared/types/bakery'
import { defineEventHandler } from 'h3'
import { fetchBakery } from '../../utils/bakery.ts'
import { toBakerySiteSettings } from '../../utils/bakery-settings.ts'

export default defineEventHandler(async (event): Promise<BakerySiteSettings> =>
  toBakerySiteSettings(
    await fetchBakery<unknown>(event, '/api/site-settings/')
  )
)
