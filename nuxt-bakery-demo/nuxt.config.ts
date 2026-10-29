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
  modules: ['@nuxtjs/i18n', 'nuxt-security'],
  devServer: { port: 3100 },
  devtools: { enabled: false },
  runtimeConfig: {
    bakeryBaseUrl: '',
    staticExport: false,
    esignApiBaseUrl: nodeProcess?.env?.ESIGN_API_BASE_URL ?? '',
    esignApiKey: nodeProcess?.env?.ESIGN_API_KEY ?? '',
  },
  nitro: {
    prerender: staticPrerenderOptions,
  },
  security: {
    strict: false,
    nonce: true,
    headers: {
      contentSecurityPolicy: {
        'default-src': ["'self'"],
        'script-src': ["'self'", "'strict-dynamic'", "'nonce-{{nonce}}'"],
        'script-src-attr': ["'none'"],
        'style-src': ["'self'", "'nonce-{{nonce}}'"],
        'style-src-attr': ["'none'"],
        'img-src': ["'self'", 'data:', 'blob:'],
        'connect-src': ["'self'"],
        'font-src': ["'self'", 'data:'],
        'frame-src': [
          "'self'",
          'https://www.youtube-nocookie.com',
          'https://player.vimeo.com',
        ],
        'media-src': ["'self'"],
        'manifest-src': ["'self'"],
        'worker-src': ["'self'", 'blob:'],
        'form-action': ["'self'"],
        'object-src': ["'none'"],
        'base-uri': ["'self'"],
        'frame-ancestors': ["'self'"],
        'upgrade-insecure-requests': true,
      },
      xFrameOptions: 'SAMEORIGIN',
      xContentTypeOptions: 'nosniff',
      referrerPolicy: 'strict-origin-when-cross-origin',
      crossOriginEmbedderPolicy: false,
      permissionsPolicy: {
        fullscreen: [
          'self',
          'https://www.youtube-nocookie.com',
          'https://player.vimeo.com',
        ],
      },
    },
    requestSizeLimiter: false,
    rateLimiter: false,
    xssValidator: false,
    corsHandler: false,
    allowedMethodsRestricter: false,
    hidePoweredBy: true,
    csrf: false,
    removeLoggers: false,
    sri: false,
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
