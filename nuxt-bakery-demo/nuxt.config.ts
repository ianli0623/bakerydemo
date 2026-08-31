export default defineNuxtConfig({
  compatibilityDate: '2026-08-21',
  css: ['~/assets/css/main.css'],
  modules: ['@nuxtjs/i18n'],
  devServer: { port: 3100 },
  devtools: { enabled: true },
  runtimeConfig: {
    bakeryBaseUrl: ''
  },
  i18n: {
    strategy: 'prefix_except_default',
    defaultLocale: 'zh-hant',
    langDir: 'locales',
    locales: [
      {
        code: 'zh-hant',
        language: 'zh-Hant',
        name: '繁體中文',
        file: 'zh-hant.json'
      },
      {
        code: 'en',
        language: 'en',
        name: 'English',
        file: 'en.json'
      }
    ]
  }
})
