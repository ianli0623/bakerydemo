<script setup lang="ts">
import type { BakerySiteSettings } from '#shared/types/bakery';
import { normalizeBakeryLocale } from '#shared/utils/locale';
import { getLocalizedSeoLinks } from '#shared/utils/localized-seo';
import { getSiteMapItems } from '~/utils/site-presentation';

const { locale, t } = useI18n();
const localePath = useLocalePath();
const localeQuery = computed(() => ({ locale: locale.value }));
const {
  data: settings,
  status,
  error,
  refresh,
} = await useFetch<BakerySiteSettings>('/api/bakery/site-settings', {
  query: localeQuery,
});

const siteMapItems = computed(() =>
  settings.value
    ? getSiteMapItems(
        settings.value.navigation,
        t('navigation.home'),
        t('navigation.contact'),
        t('navigation.siteMap'),
        t('siteMap.complianceRegistry'),
        (label, destination) =>
          t(`siteMap.linkDescriptions.${destination}`, { label }),
      )
    : [],
);
const errorMessage = computed(() =>
  error.value?.statusCode === 500
    ? t('status.configurationError')
    : t('status.cmsUnavailable'),
);
const pageTitle = computed(
  () =>
    `${t('siteMap.title')} | ${settings.value?.title_suffix || 'SEMI E187'}`,
);
const requestOrigin = useRequestURL().origin;
const seoLinks = computed(() =>
  getLocalizedSeoLinks(
    requestOrigin,
    normalizeBakeryLocale(locale.value),
    'sitemap',
  ),
);

useSeoMeta({
  title: () => pageTitle.value,
  description: () => t('siteMap.introduction'),
});
useHead(() => ({
  link: [
    { rel: 'canonical', href: seoLinks.value.canonical },
    ...seoLinks.value.alternatives.map((alternative) => ({
      rel: 'alternate' as const,
      type: 'text/html',
      hreflang: alternative.hreflang,
      href: alternative.href,
    })),
  ],
}));
</script>

<template>
  <main
    id="main-content"
    class="page-container sitemap-page"
    aria-labelledby="sitemap-heading"
  >
    <header class="sitemap-hero">
      <p class="section-kicker">{{ t('siteMap.eyebrow') }}</p>
      <h1 id="sitemap-heading">{{ t('siteMap.title') }}</h1>
      <p class="section-introduction">{{ t('siteMap.introduction') }}</p>
    </header>

    <section class="sitemap-guide" aria-labelledby="sitemap-regions-heading">
      <h2 id="sitemap-regions-heading">{{ t('siteMap.regionsHeading') }}</h2>
      <p>{{ t('siteMap.regionsIntroduction') }}</p>
      <ol class="sitemap-region-list">
        <li>{{ t('siteMap.regions.upper') }}</li>
        <li>{{ t('siteMap.regions.central') }}</li>
        <li>{{ t('siteMap.regions.footer') }}</li>
      </ol>

      <h2>{{ t('siteMap.accessKeysHeading') }}</h2>
      <p>{{ t('siteMap.accessKeysIntroduction') }}</p>
      <ul class="sitemap-accesskey-list">
        <li>
          <kbd>Alt</kbd> + <kbd>U</kbd>{{ t('siteMap.accessKeysSeparator') }}
          {{ t('siteMap.accessKeys.upper') }}
        </li>
        <li>
          <kbd>Alt</kbd> + <kbd>C</kbd>{{ t('siteMap.accessKeysSeparator') }}
          {{ t('siteMap.accessKeys.central') }}
        </li>
        <li>
          <kbd>Alt</kbd> + <kbd>Z</kbd>{{ t('siteMap.accessKeysSeparator') }}
          {{ t('siteMap.accessKeys.footer') }}
        </li>
        <li>
          <kbd>Tab</kbd>{{ t('siteMap.accessKeysSeparator') }}
          {{ t('siteMap.accessKeys.tab') }}
        </li>
      </ul>
      <p class="sitemap-browser-note">{{ t('siteMap.browserNote') }}</p>
    </section>

    <div v-if="status === 'pending'" class="state-panel" role="status">
      <strong>{{ t('status.loading') }}</strong>
    </div>

    <div
      v-else-if="error || !settings"
      class="state-panel state-error"
      role="alert"
    >
      <div>
        <strong>{{ t('status.navigationError') }}</strong>
        <p>{{ errorMessage }}</p>
      </div>
      <button type="button" class="button button-secondary" @click="refresh()">
        {{ t('status.retry') }}
      </button>
    </div>

    <section
      v-else
      class="sitemap-features"
      aria-labelledby="sitemap-features-heading"
    >
      <h2 id="sitemap-features-heading">
        {{ t('siteMap.mainFunctionsHeading') }}
      </h2>
      <nav class="sitemap-list-nav" :aria-label="t('siteMap.label')">
        <ol class="sitemap-list">
          <li v-for="(item, index) in siteMapItems" :key="item.id">
            <NuxtLink
              :to="
                item.path.startsWith('#') ? item.path : localePath(item.path)
              "
              :title="item.description"
              :aria-label="item.description"
            >
              <span class="sitemap-list__number">{{ index + 1 }}</span>
              <span>{{ item.label }}</span>
            </NuxtLink>
            <ol v-if="item.children?.length" class="sitemap-sublist">
              <li v-for="(child, childIndex) in item.children" :key="child.id">
                <NuxtLink
                  :to="localePath(child.path)"
                  :title="child.description"
                  :aria-label="child.description"
                >
                  <span class="sitemap-list__number">
                    {{ index + 1 }}-{{ childIndex + 1 }}
                  </span>
                  <span>{{ child.label }}</span>
                </NuxtLink>
              </li>
            </ol>
          </li>
        </ol>
      </nav>
    </section>
  </main>
</template>
