<script setup lang="ts">
import type { BakerySiteSettings } from '#shared/types/bakery'
import {
  getContactLinks,
  getFooterLogoPresentation,
  isNavigationItemActive,
  reduceNavigationOpen
} from '~/utils/site-presentation'

const route = useRoute()
const { data: settings, error: settingsError } =
  await useFetch<BakerySiteSettings>('/api/bakery/site-settings')

const navigationOpen = ref(false)
const toggleNavigation = () => {
  navigationOpen.value = reduceNavigationOpen(navigationOpen.value, 'toggle')
}
const closeNavigation = (event: 'escape' | 'route') => {
  navigationOpen.value = reduceNavigationOpen(navigationOpen.value, event)
}

watch(() => route.path, () => closeNavigation('route'))

const onWindowKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    closeNavigation('escape')
  }
}

onMounted(() => window.addEventListener('keydown', onWindowKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onWindowKeydown))

const contactLinks = computed(() =>
  settings.value ? getContactLinks(settings.value.contact) : null
)
const footerLogo = computed(() =>
  getFooterLogoPresentation(settings.value?.footer_logo ?? null)
)
</script>

<template>
  <div class="site-shell">
    <a class="skip-link" href="#main-content">跳到主要內容</a>

    <header class="site-header">
      <div class="site-header-inner">
        <NuxtLink
          class="brand"
          to="/"
          :aria-label="`${settings?.site_name || 'SEMI E187'}首頁`"
          @click="closeNavigation('route')"
        >
          <span class="brand-copy">
            <strong>SEMI E187</strong>
            <small>認驗證制度</small>
          </span>
        </NuxtLink>

        <button
          type="button"
          class="nav-toggle"
          aria-controls="primary-navigation"
          :aria-expanded="navigationOpen"
          @click="toggleNavigation"
        >
          <span class="nav-toggle__label">選單</span>
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
          aria-label="主要導覽"
        >
          <NuxtLink
            v-for="item in settings?.navigation || []"
            :key="item.id"
            class="nav-link"
            :to="item.path"
            :aria-current="
              isNavigationItemActive(item.path, route.path) ? 'page' : undefined
            "
            @click="closeNavigation('route')"
          >
            {{ item.title }}
          </NuxtLink>
          <a class="nav-contact" href="#contact" @click="closeNavigation('route')">
            聯絡我們
          </a>
          <span v-if="settingsError" class="nav-status" role="status">
            選單暫時無法載入
          </span>
        </nav>
      </div>
    </header>

    <NuxtPage />

    <footer id="contact" class="site-footer" aria-labelledby="contact-heading">
      <div class="footer-accent" aria-hidden="true" />
      <div class="footer-inner">
        <div class="footer-introduction">
          <p class="footer-kicker">CONTACT US</p>
          <h2 id="contact-heading">
            {{ settings?.contact.heading || '半導體智慧製造資安合規諮詢' }}
          </h2>
          <p>
            配合數位發展部推動產業資安跨域聯防，協助本土半導體設備廠與資安供應鏈進行生態鏈結。若您對 SEMI E187 認驗證程序有任何合規輔導或技術細節疑問，歡迎與專案推動辦公室聯絡。
          </p>
        </div>

        <address v-if="settings && contactLinks" class="contact-card">
          <h3>{{ settings.contact.name }}</h3>
          <p>{{ settings.contact.context }}</p>
          <a
            v-if="contactLinks.phone && settings.contact.phone"
            :href="contactLinks.phone"
          >
            <span>電話</span>{{ settings.contact.phone }}
          </a>
          <a
            v-if="contactLinks.email && settings.contact.email"
            :href="contactLinks.email"
          >
            <span>信箱</span>{{ settings.contact.email }}
          </a>
          <p v-if="!contactLinks.phone && !contactLinks.email">聯絡資訊即將提供</p>
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
            >
            <strong v-else>{{ settings?.site_name || 'SEMI E187' }}</strong>
          </div>
          <p class="footer-copyright">
            {{ settings?.organisation_text || 'SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme.' }}
          </p>
          <nav v-if="settings?.navigation.length" aria-label="頁尾導覽">
            <NuxtLink
              v-for="item in settings.navigation"
              :key="item.id"
              :to="item.path"
              :aria-current="
                isNavigationItemActive(item.path, route.path) ? 'page' : undefined
              "
            >
              {{ item.title }}
            </NuxtLink>
          </nav>
        </div>
      </div>
    </footer>
  </div>
</template>
