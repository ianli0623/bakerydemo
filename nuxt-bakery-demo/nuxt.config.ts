export default defineNuxtConfig({
  compatibilityDate: '2026-08-21',
  css: ['~/assets/css/main.css'],
  devServer: { port: 3100 },
  devtools: { enabled: true },
  runtimeConfig: {
    bakeryBaseUrl: ''
  }
})
