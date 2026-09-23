<script setup lang="ts">
import {
  getLanguageLinkLang,
  readStoredFontScale,
  reduceFontScale,
  type FontScale,
  type FontScaleAction,
  writeStoredFontScale,
} from '~/utils/accessibility';

const { locale, t } = useI18n();
const localePath = useLocalePath();
const switchLocalePath = useSwitchLocalePath();
const fontScale = ref<FontScale>('default');

function applyFontScale(value: FontScale, persist = true) {
  fontScale.value = value;

  if (!import.meta.client) {
    return;
  }

  document.documentElement.dataset.fontScale = value;
  document.documentElement.classList.remove(
    'font-scale--small',
    'font-scale--default',
    'font-scale--large',
  );
  document.documentElement.classList.add(`font-scale--${value}`);
  if (persist) {
    writeStoredFontScale(window.localStorage, value);
  }
}

function updateFontScale(action: FontScaleAction) {
  applyFontScale(reduceFontScale(fontScale.value, action));
}

onMounted(() => {
  applyFontScale(readStoredFontScale(window.localStorage), false);
});
</script>

<template>
  <aside class="accessibility-toolbar" :aria-label="t('accessibility.toolbar')">
    <div class="accessibility-toolbar__inner">
      <div class="accessibility-toolbar__controls">
        <a href="#main-content">{{ t('accessibility.skipToContent') }}</a>
        <span class="accessibility-toolbar__separator" aria-hidden="true"
          >|</span
        >
        <span>{{ t('accessibility.fontSize') }}</span>
        <button
          type="button"
          :aria-label="t('accessibility.fontLarger')"
          :aria-pressed="fontScale === 'large'"
          @click="updateFontScale('increase')"
        >
          A+
        </button>
        <button
          type="button"
          :aria-label="t('accessibility.fontReset')"
          :aria-pressed="fontScale === 'default'"
          @click="updateFontScale('reset')"
        >
          A
        </button>
        <button
          type="button"
          :aria-label="t('accessibility.fontSmaller')"
          :aria-pressed="fontScale === 'small'"
          @click="updateFontScale('decrease')"
        >
          A-
        </button>
      </div>

      <div class="accessibility-toolbar__links">
        <NuxtLink
          class="accessibility-toolbar__sitemap"
          :to="localePath('/sitemap/')"
        >
          {{ t('navigation.siteMap') }}
        </NuxtLink>
        <span class="accessibility-toolbar__separator" aria-hidden="true"
          >|</span
        >
        <div
          class="accessibility-toolbar__locales"
          role="group"
          :aria-label="t('language.label')"
        >
          <NuxtLink
            :to="switchLocalePath('zh-tw')"
            :lang="getLanguageLinkLang(locale, 'zh-tw')"
            :aria-current="locale === 'zh-tw' ? 'page' : undefined"
          >
            {{ t('language.traditionalChinese') }}
          </NuxtLink>
          <NuxtLink
            :to="switchLocalePath('en')"
            :lang="getLanguageLinkLang(locale, 'en')"
            :aria-current="locale === 'en' ? 'page' : undefined"
          >
            {{ t('language.english') }}
          </NuxtLink>
        </div>
      </div>
    </div>
  </aside>
</template>
