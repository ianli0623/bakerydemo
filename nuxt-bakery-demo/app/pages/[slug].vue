<script setup lang="ts">
import type { BakeryStandardPage } from '#shared/types/bakery'
import { isMissingBakeryPageError, isValidStandardPageSlug } from '#shared/utils/bakery'
import { getStandardPagePresentation } from '~/utils/site-presentation'

const route = useRoute()
const slug = computed(() => String(route.params.slug ?? ''))

function missingPageError() {
  return createError({
    statusCode: 404,
    statusMessage: '找不到指定的已發布頁面。'
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
  await useFetch<BakeryStandardPage>(requestUrl)

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

useSeoMeta({
  title: () => page.value?.meta.seo_title || page.value?.title || 'SEMI E187',
  description: () =>
    page.value?.meta.search_description || page.value?.introduction || ''
})
</script>

<template>
  <main
    id="main-content"
    class="page-container standard-page"
    :class="`standard-page--${slug}`"
    aria-live="polite"
  >
    <div v-if="status === 'pending'" class="standard-loading" aria-label="頁面載入中">
      <div class="skeleton skeleton-line skeleton-line-short" />
      <div class="skeleton skeleton-title" />
      <div class="skeleton skeleton-hero" />
    </div>

    <div v-else-if="error" class="state-panel state-error" role="alert">
      <div>
        <strong>頁面讀取失敗</strong>
        <p>目前無法連線到 Bakery CMS，請確認 Wagtail 已啟動。</p>
      </div>
      <button class="button button-secondary" type="button" @click="refresh()">
        再試一次
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
            />
          </div>
        </div>
      </section>
    </article>
  </main>
</template>
