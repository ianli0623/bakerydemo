<script setup lang="ts">
import type {
  BakeryHomeViewModel,
  BakerySiteSettings
} from '#shared/types/bakery'
import { normalizeBakeryLocale } from '#shared/utils/locale'
import CardGrid from '~/components/blocks/CardGrid.vue'
import {
  getLocalizedSeoLinks,
  getPageSeoPresentation
} from '#shared/utils/localized-seo'
import { partitionHomeBlocks } from '~/utils/site-presentation'

const { locale, t } = useI18n()
const localeQuery = computed(() => ({ locale: locale.value }))
const { data: home, status, error, refresh } =
  await useFetch<BakeryHomeViewModel>('/api/bakery/home', {
    query: localeQuery
  })
const { data: settings } =
  await useFetch<BakerySiteSettings>('/api/bakery/site-settings', {
    query: localeQuery
  })

const homePresentation = computed(() =>
  partitionHomeBlocks(home.value?.body ?? [])
)

const errorMessage = computed(() =>
  error.value?.statusCode === 500
    ? t('status.configurationError')
    : t('status.cmsUnavailable')
)

const seoPresentation = computed(() => getPageSeoPresentation(
  {
    title: home.value?.title || settings.value?.site_name || 'SEMI E187',
    seoTitle: home.value?.meta.seo_title || '',
    searchDescription: home.value?.meta.search_description || '',
    introduction: home.value?.hero_text || ''
  },
  settings.value?.title_suffix || ''
))
const requestOrigin = useRequestURL().origin
const seoLinks = computed(() => getLocalizedSeoLinks(
  requestOrigin,
  normalizeBakeryLocale(locale.value)
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
  <main id="main-content" class="page-container home-page" aria-live="polite">
    <div
      v-if="status === 'pending'"
      class="home-loading"
      :aria-label="t('status.homeLoading')"
    >
      <div class="skeleton skeleton-hero" />
      <div class="skeleton skeleton-line skeleton-line-short" />
      <div class="skeleton skeleton-line" />
    </div>

    <div v-else-if="error" class="state-panel state-error" role="alert">
      <div>
        <strong>{{ t('status.homeLoadError') }}</strong>
        <p>{{ errorMessage }}</p>
      </div>
      <button class="button button-secondary" type="button" @click="refresh()">
        {{ t('status.retry') }}
      </button>
    </div>

    <div v-else-if="!home" class="state-panel">
      <div>
        <strong>{{ t('status.homeMissingTitle') }}</strong>
        <p>{{ t('status.homeMissing') }}</p>
      </div>
    </div>

    <template v-else>
      <section class="home-hero" aria-labelledby="home-title">
        <div class="home-hero-pattern" aria-hidden="true" />
        <div
          class="home-hero-inner"
          :class="{ 'home-hero-inner--single': !homePresentation.newsBlock }"
        >
          <div class="home-hero-content">
            <p class="hero-badge">
              <span aria-hidden="true" />
              {{ home.hero_badge }}
            </p>
            <h1 id="home-title">{{ home.title }}</h1>
            <p v-if="settings?.site_tagline" class="hero-tagline">
              {{ settings.site_tagline }}
            </p>
            <p class="hero-description">{{ home.hero_text }}</p>
            <div class="hero-actions">
              <NuxtLink
                v-if="home.hero_cta && home.heroCtaPath"
                class="button button-primary"
                :to="home.heroCtaPath"
              >
                {{ home.hero_cta }}
                <span aria-hidden="true">→</span>
              </NuxtLink>
              <NuxtLink
                v-if="home.secondary_hero_cta && home.secondaryHeroCtaPath"
                class="button button-dark"
                :to="home.secondaryHeroCtaPath"
              >
                {{ home.secondary_hero_cta }}
                <span aria-hidden="true">→</span>
              </NuxtLink>
            </div>
          </div>

          <aside
            v-if="homePresentation.newsBlock"
            class="home-news"
            :aria-label="homePresentation.newsBlock.value.heading"
          >
            <CardGrid :value="homePresentation.newsBlock.value" />
          </aside>
        </div>
      </section>

      <div v-if="homePresentation.remainingBlocks.length" class="home-body">
        <StreamField :blocks="homePresentation.remainingBlocks" />
      </div>
    </template>
  </main>
</template>
