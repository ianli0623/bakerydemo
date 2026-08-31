<script setup lang="ts">
import type { BakerySiteSettings, BakeryStandardPage } from '#shared/types/bakery'
import { isMissingBakeryPageError, isValidStandardPageSlug } from '#shared/utils/bakery'
import { normalizeBakeryLocale } from '#shared/utils/locale'
import {
  getLocalizedSeoLinks,
  getPageSeoPresentation
} from '#shared/utils/localized-seo'
import { getStandardPagePresentation } from '~/utils/site-presentation'

const route = useRoute()
const { locale, t } = useI18n()
const slug = computed(() => String(route.params.slug ?? ''))
const localeQuery = computed(() => ({ locale: locale.value }))

function missingPageError() {
  return createError({
    statusCode: 404,
    statusMessage: t('status.notFound')
  })
}

if (!isValidStandardPageSlug(route.params.slug)) {
  throw missingPageError()
}

watch(slug, (value) => {
  if (!isValidStandardPageSlug(value)) {
    showError(missingPageError())
  }
})

const requestUrl = computed(
  () => `/api/bakery/pages/${encodeURIComponent(slug.value)}`
)

const { data: page, status, error, refresh } =
  await useFetch<BakeryStandardPage>(requestUrl, { query: localeQuery })
const { data: settings } =
  await useFetch<BakerySiteSettings>('/api/bakery/site-settings', {
    query: localeQuery
  })

const presentation = computed(() =>
  page.value ? getStandardPagePresentation(slug.value, page.value) : null
)
const reservedSectionAnchors = computed(() =>
  presentation.value?.sections.map(section => section.anchorId) ?? []
)

if (isMissingBakeryPageError(error.value)) {
  throw missingPageError()
}

watch(error, (value) => {
  if (isMissingBakeryPageError(value)) {
    showError(missingPageError())
  }
})

const seoPresentation = computed(() => getPageSeoPresentation(
  {
    title: page.value?.title || 'SEMI E187',
    seoTitle: page.value?.meta.seo_title || '',
    searchDescription: page.value?.meta.search_description || '',
    introduction: page.value?.introduction || ''
  },
  settings.value?.title_suffix || ''
))
const requestOrigin = useRequestURL().origin
const seoLinks = computed(() => getLocalizedSeoLinks(
  requestOrigin,
  normalizeBakeryLocale(locale.value),
  slug.value
))

useSeoMeta({
  title: () => seoPresentation.value.title,
  description: () => seoPresentation.value.description
})
useHead(() => ({
  link: [
    { rel: 'canonical', href: seoLinks.value.canonical },
    ...seoLinks.value.alternatives.map(alternative => ({
      rel: 'alternate' as const,
      type: 'text/html',
      hreflang: alternative.hreflang,
      href: alternative.href
    }))
  ]
}))
</script>

<template>
  <main
    id="main-content"
    class="page-container standard-page"
    :class="`standard-page--${slug}`"
    aria-live="polite"
  >
    <div
      v-if="status === 'pending'"
      class="standard-loading"
      :aria-label="t('status.pageLoading')"
    >
      <div class="skeleton skeleton-line skeleton-line-short" />
      <div class="skeleton skeleton-title" />
      <div class="skeleton skeleton-hero" />
    </div>

    <div v-else-if="error" class="state-panel state-error" role="alert">
      <div>
        <strong>{{ t('status.pageLoadError') }}</strong>
        <p>{{ t('status.cmsUnavailable') }}</p>
      </div>
      <button class="button button-secondary" type="button" @click="refresh()">
        {{ t('status.retry') }}
      </button>
    </div>

    <article v-else-if="page && presentation" class="standard-sections">
      <section
        v-for="(section, sectionIndex) in presentation.sections"
        :id="section.anchorId"
        :key="section.anchorId"
        class="standard-section"
        :class="[
          `standard-section--${section.layout}`,
          `standard-section--${section.surface}`
        ]"
        :aria-labelledby="section.headingId"
      >
        <div class="standard-section__inner">
          <header class="standard-section__intro">
            <p class="section-kicker">{{ section.kicker }}</p>
            <component
              :is="sectionIndex === 0 ? 'h1' : 'h2'"
              :id="section.headingId"
              class="standard-section__title"
            >
              {{ section.title }}
            </component>
            <!-- Published editor-managed Wagtail rich text is trusted here. -->
            <div
              v-if="section.introductionHtml"
              class="standard-section__description rich-text"
              v-html="section.introductionHtml"
            />
            <p
              v-else-if="section.introduction"
              class="standard-section__description"
            >
              {{ section.introduction }}
            </p>
          </header>

          <div v-if="section.body.length" class="standard-section__body">
            <StreamField
              :blocks="section.body"
              :reserved-anchors="reservedSectionAnchors"
              :page-slug="slug"
            />
          </div>
        </div>
      </section>
    </article>
  </main>
</template>
