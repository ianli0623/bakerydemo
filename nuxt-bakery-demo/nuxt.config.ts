import { getStaticPrerenderOptions } from './shared/utils/locale.ts';

const nodeProcess = Reflect.get(globalThis, 'process') as
  | { env?: Record<string, string | undefined> }
  | undefined;
const staticPrerenderOptions = getStaticPrerenderOptions(
  nodeProcess?.env?.NUXT_STATIC_EXPORT === 'true',
);

export default defineNuxtConfig({
  compatibilityDate: '2026-08-21',
  css: ['~/assets/css/main.css'],
  modules: ['@nuxtjs/i18n'],
  devServer: { port: 3100 },
  devtools: { enabled: false },
  runtimeConfig: {
    bakeryBaseUrl: '',
    staticExport: false,
  },
  nitro: {
    prerender: staticPrerenderOptions,
  },
  i18n: {
    strategy: 'prefix',
    defaultLocale: 'en',
    rootRedirect: {
      path: '/en/',
      statusCode: 301,
    },
    detectBrowserLanguage: false,
    langDir: 'locales',
    locales: [
      {
        code: 'zh-tw',
        language: 'zh-Hant',
        name: '繁體中文',
        file: 'zh-hant.json',
      },
      {
        code: 'en',
        language: 'en',
        name: 'English',
        file: 'en.json',
      },
    ],
  },
});
