<script setup lang="ts">
import type {
  BakeryHomeViewModel,
  BakerySiteSettings
} from '#shared/types/bakery'
import CardGrid from '~/components/blocks/CardGrid.vue'
import { partitionHomeBlocks } from '~/utils/site-presentation'

const { data: home, status, error, refresh } =
  await useFetch<BakeryHomeViewModel>('/api/bakery/home')
const { data: settings } =
  await useFetch<BakerySiteSettings>('/api/bakery/site-settings')

const homePresentation = computed(() =>
  partitionHomeBlocks(home.value?.body ?? [])
)

const errorMessage = computed(() =>
  error.value?.statusCode === 500
    ? 'Bakery API 尚未設定，請檢查 NUXT_BAKERY_BASE_URL。'
    : '目前無法連線到 Bakery CMS，請確認 Wagtail 已啟動。'
)

useSeoMeta({
  title: () => home.value?.meta.seo_title || home.value?.title || 'SEMI E187',
  description: () =>
    home.value?.meta.search_description
    || home.value?.hero_text
    || '半導體設備資安標準認驗證制度。'
})
</script>

<template>
  <main id="main-content" class="page-container home-page" aria-live="polite">
    <div v-if="status === 'pending'" class="home-loading" aria-label="首頁載入中">
      <div class="skeleton skeleton-hero" />
      <div class="skeleton skeleton-line skeleton-line-short" />
      <div class="skeleton skeleton-line" />
    </div>

    <div v-else-if="error" class="state-panel state-error" role="alert">
      <div>
        <strong>首頁讀取失敗</strong>
        <p>{{ errorMessage }}</p>
      </div>
      <button class="button button-secondary" type="button" @click="refresh()">
        再試一次
      </button>
    </div>

    <div v-else-if="!home" class="state-panel">
      <div>
        <strong>尚未取得首頁內容</strong>
        <p>請確認 Wagtail 首頁已發布。</p>
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
              標準認知 × 技術資源 × 驗證合規
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
                class="button button-dark"
                to="/certification/#certified-list"
              >
                合規設備清單
                <span aria-hidden="true">→</span>
              </NuxtLink>
            </div>
          </div>

          <aside
            v-if="homePresentation.newsBlock"
            class="home-news"
            aria-label="最新消息"
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
