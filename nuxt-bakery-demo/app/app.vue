<script setup lang="ts">
import type { BakerySiteSettings } from '#shared/types/bakery';
import { getLanguageLinkLang } from '~/utils/accessibility';
import {
  getContactLinks,
  getFooterLogoPresentation,
  getNavigationItemLabel,
  isNavigationItemActive,
  reduceNavigationOpen,
} from '~/utils/site-presentation';

const route = useRoute();
const { locale, t } = useI18n();
const localePath = useLocalePath();
const switchLocalePath = useSwitchLocalePath();
const localeQuery = computed(() => ({ locale: locale.value }));
const { data: settings, error: settingsError } =
  await useFetch<BakerySiteSettings>('/api/bakery/site-settings', {
    query: localeQuery,
  });

useHead(() => ({
  htmlAttrs: { lang: locale.value === 'en' ? 'en' : 'zh-Hant' },
}));

const navigationOpen = ref(false);
const toggleNavigation = () => {
  navigationOpen.value = reduceNavigationOpen(navigationOpen.value, 'toggle');
};
const closeNavigation = (event: 'escape' | 'route') => {
  navigationOpen.value = reduceNavigationOpen(navigationOpen.value, event);
};

watch(
  () => route.path,
  () => closeNavigation('route'),
);

const onWindowKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    closeNavigation('escape');
  }
};

onMounted(() => window.addEventListener('keydown', onWindowKeydown));
onBeforeUnmount(() => window.removeEventListener('keydown', onWindowKeydown));

const contactLinks = computed(() =>
  settings.value ? getContactLinks(settings.value.contact) : null,
);
const footerLogo = computed(() =>
  getFooterLogoPresentation(settings.value?.footer_logo ?? null),
);
</script>

<template>
  <div class="site-shell">
    <a class="skip-link" href="#main-content">
      {{ t('accessibility.skipToContent') }}
    </a>

    <AccessibilityToolbar />

    <header class="site-header">
      <a
        id="accesskey-u"
        class="accesskey-marker accesskey-marker--upper"
        href="#accesskey-u"
        accesskey="U"
        :title="t('accessibility.upperRegion')"
        :aria-label="t('accessibility.upperRegion')"
        >:::</a
      >
      <div class="site-header-inner">
        <NuxtLink
          class="brand"
          :to="localePath('/')"
          :aria-label="`${settings?.site_name || 'SEMI E187'} — ${t('navigation.home')}`"
          @click="closeNavigation('route')"
        >
          <span class="brand-copy">
            <strong>{{ settings?.title_suffix || 'SEMI E187' }}</strong>
            <small v-if="settings?.brand_label">{{
              settings.brand_label
            }}</small>
          </span>
        </NuxtLink>

        <button
          type="button"
          class="nav-toggle"
          aria-controls="primary-navigation"
          :aria-expanded="navigationOpen"
          @click="toggleNavigation"
        >
          <span class="nav-toggle__label">
            {{
              navigationOpen
                ? t('navigation.closeMenu')
                : t('navigation.openMenu')
            }}
          </span>
          <span class="nav-toggle__icon" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
        </button>

        <nav
          id="primary-navigation"
          class="site-nav"
          :class="{ 'site-nav--open': navigationOpen }"
          :aria-label="t('navigation.label')"
        >
          <NuxtLink
            v-for="item in settings?.navigation || []"
            :key="item.id"
            class="nav-link"
            :to="localePath(item.slug ? `/${item.slug}/` : '/')"
            :aria-current="
              isNavigationItemActive(item.path, route.path) ? 'page' : undefined
            "
            @click="closeNavigation('route')"
          >
            {{ getNavigationItemLabel(item, t('navigation.home')) }}
          </NuxtLink>
          <a
            class="nav-contact"
            href="#contact"
            @click="closeNavigation('route')"
          >
            {{ t('navigation.contact') }}
          </a>
          <NuxtLink
            class="nav-link nav-sitemap"
            :to="localePath('/sitemap/')"
            :aria-current="
              isNavigationItemActive(localePath('/sitemap/'), route.path)
                ? 'page'
                : undefined
            "
            @click="closeNavigation('route')"
          >
            {{ t('navigation.siteMap') }}
          </NuxtLink>
          <div
            class="mobile-language-switch"
            role="group"
            :aria-label="t('mobile.language')"
          >
            <span>{{ t('language.label') }}</span>
            <NuxtLink
              :to="switchLocalePath('zh-tw')"
              :lang="getLanguageLinkLang(locale, 'zh-tw')"
              :aria-current="locale === 'zh-tw' ? 'page' : undefined"
              @click="closeNavigation('route')"
            >
              {{ t('language.traditionalChinese') }}
            </NuxtLink>
            <NuxtLink
              :to="switchLocalePath('en')"
              :lang="getLanguageLinkLang(locale, 'en')"
              :aria-current="locale === 'en' ? 'page' : undefined"
              @click="closeNavigation('route')"
            >
              {{ t('language.english') }}
            </NuxtLink>
          </div>
          <span v-if="settingsError" class="nav-status" role="status">
            {{ t('status.navigationError') }}
          </span>
        </nav>
      </div>
    </header>

    <a
      id="accesskey-c"
      class="accesskey-marker accesskey-marker--content"
      href="#main-content"
      accesskey="C"
      :title="t('accessibility.centralRegion')"
      :aria-label="t('accessibility.centralRegion')"
      >:::</a
    >

    <NuxtPage />

    <footer id="contact" class="site-footer" aria-labelledby="contact-heading">
      <a
        id="accesskey-z"
        class="accesskey-marker accesskey-marker--footer"
        href="#contact-heading"
        accesskey="Z"
        :title="t('accessibility.footerRegion')"
        :aria-label="t('accessibility.footerRegion')"
        >:::</a
      >
      <div class="footer-accent" aria-hidden="true" />
      <div class="footer-inner">
        <div class="footer-introduction">
          <p class="footer-kicker">{{ t('navigation.contact') }}</p>
          <h2 id="contact-heading">
            {{ settings?.contact.heading || t('contact.headingFallback') }}
          </h2>
          <p v-if="settings?.footer_introduction">
            {{ settings.footer_introduction }}
          </p>
        </div>

        <address v-if="settings && contactLinks" class="contact-card">
          <h3>{{ settings.contact.name }}</h3>
          <p>{{ settings.contact.context }}</p>
          <a
            v-if="contactLinks.phone && settings.contact.phone"
            :href="contactLinks.phone"
          >
            <span>{{ t('contact.phone') }}</span
            >{{ settings.contact.phone }}
          </a>
          <a
            v-if="contactLinks.email && settings.contact.email"
            :href="contactLinks.email"
          >
            <span>{{ t('contact.email') }}</span
            >{{ settings.contact.email }}
          </a>
          <p v-if="!contactLinks.phone && !contactLinks.email">
            {{ t('status.unavailable') }}
          </p>
        </address>

        <div class="footer-bottom">
          <div class="footer-brand">
            <img
              v-if="footerLogo"
              :src="footerLogo.src"
              :width="footerLogo.width"
              :height="footerLogo.height"
              :alt="footerLogo.alt"
              loading="lazy"
            />
            <strong v-else>{{ settings?.site_name || 'SEMI E187' }}</strong>
          </div>
          <p class="footer-copyright">
            {{
              settings?.organisation_text ||
              settings?.title_suffix ||
              'SEMI E187'
            }}
          </p>
          <nav :aria-label="t('navigation.footer')">
            <NuxtLink
              v-for="item in settings?.navigation || []"
              :key="item.id"
              :to="localePath(item.slug ? `/${item.slug}/` : '/')"
              :aria-current="
                isNavigationItemActive(item.path, route.path)
                  ? 'page'
                  : undefined
              "
            >
              {{ getNavigationItemLabel(item, t('navigation.home')) }}
            </NuxtLink>
            <NuxtLink :to="localePath('/sitemap/')">
              {{ t('navigation.siteMap') }}
            </NuxtLink>
          </nav>
        </div>
      </div>
    </footer>
  </div>
</template>
