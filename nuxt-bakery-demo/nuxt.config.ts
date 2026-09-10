export default defineNuxtConfig({
  compatibilityDate: '2026-08-21',
  css: ['~/assets/css/main.css'],
  modules: ['@nuxtjs/i18n'],
  devServer: { port: 3100 },
  devtools: { enabled: false },
  runtimeConfig: {
    bakeryBaseUrl: '',
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
