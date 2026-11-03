export default defineNitroPlugin((nitroApp) => {
  let cmsOrigin: string;
  try {
    const cmsUrl = new URL(useRuntimeConfig().bakeryBaseUrl);
    if (cmsUrl.protocol !== 'http:' && cmsUrl.protocol !== 'https:') return;
    cmsOrigin = cmsUrl.origin;
  } catch {
    return;
  }

  // Read the runtime setting so one build works with each server's CMS origin.
  // Only images gain this source; the strict script/style policy stays intact.
  // Nuxt Security registers its header handler after application plugins.
  nitroApp.hooks.hook('nuxt-security:ready', async () => {
    await nitroApp.hooks.callHook('nuxt-security:headers', {
      route: '/**',
      headers: {
        contentSecurityPolicy: {
          'img-src': ["'self'", 'data:', 'blob:', cmsOrigin],
        },
      },
    });
  });
});
