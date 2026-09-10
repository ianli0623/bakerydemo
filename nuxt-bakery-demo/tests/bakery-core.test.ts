import assert from 'node:assert/strict';
import test from 'node:test';
import type { H3Event } from 'h3';
import {
  getUpstreamStatus,
  normalizeBaseUrl,
  resolvePayloadMediaUrls,
  resolveMediaUrl,
  toBakeryErrorDetails,
} from '../server/utils/bakery-core.ts';
import { fetchBakery } from '../server/utils/bakery.ts';

test('normalizeBaseUrl accepts HTTP origins and removes trailing slashes', () => {
  assert.equal(
    normalizeBaseUrl(' http://127.0.0.1:8000/// '),
    'http://127.0.0.1:8000',
  );
  assert.equal(
    normalizeBaseUrl('https://cms.example.com/tenant/'),
    'https://cms.example.com/tenant',
  );
});

test('normalizeBaseUrl rejects empty and non-HTTP values', () => {
  assert.throws(() => normalizeBaseUrl(''), /NUXT_BAKERY_BASE_URL/);
  assert.throws(() => normalizeBaseUrl('file:///tmp/cms'), /HTTP/);
});

test('resolveMediaUrl preserves absolute URLs and joins relative media paths', () => {
  assert.equal(
    resolveMediaUrl(
      'http://127.0.0.1:8000',
      'http://localhost:8000/media/a.jpg',
    ),
    'http://localhost:8000/media/a.jpg',
  );
  assert.equal(
    resolveMediaUrl('http://127.0.0.1:8000', '/media/a.jpg'),
    'http://127.0.0.1:8000/media/a.jpg',
  );
  assert.equal(resolveMediaUrl('http://127.0.0.1:8000', null), null);
});

test('resolvePayloadMediaUrls rebuilds rendition full_url values from configured CMS', () => {
  const payload = {
    body: [
      {
        value: {
          image: {
            meta: {
              rendition: {
                url: '/media/images/test.width-600.jpg',
                full_url: 'http://localhost:8000/media/images/stale.jpg',
                width: 600,
                height: 338,
                alt: 'Test',
              },
            },
          },
        },
      },
    ],
    preserved: {
      url: '/ordinary-link/',
      full_url: 'https://example.com/ordinary-link/',
    },
  };

  const normalized = resolvePayloadMediaUrls(
    payload,
    'http://127.0.0.1:8000',
  ) as typeof payload & {
    body: Array<{
      value: {
        image: {
          meta: { rendition: { full_url: string } };
        };
      };
    }>;
  };

  assert.equal(
    normalized.body[0]?.value.image.meta.rendition.full_url,
    'http://127.0.0.1:8000/media/images/test.width-600.jpg',
  );
  assert.equal(
    normalized.preserved.full_url,
    'https://example.com/ordinary-link/',
  );
});

test('getUpstreamStatus reads fetch and H3 error shapes', () => {
  assert.equal(getUpstreamStatus({ response: { status: 404 } }), 404);
  assert.equal(getUpstreamStatus({ statusCode: 400 }), 400);
  assert.equal(getUpstreamStatus(new Error('offline')), undefined);
});

test('toBakeryErrorDetails preserves known statuses and maps outages to 502', () => {
  assert.deepEqual(toBakeryErrorDetails({ response: { status: 404 } }), {
    statusCode: 404,
    statusMessage: '找不到指定的已發布頁面。',
  });
  assert.deepEqual(toBakeryErrorDetails({ response: { status: 400 } }), {
    statusCode: 400,
    statusMessage: 'Bakery API 查詢參數不正確。',
  });
  assert.deepEqual(toBakeryErrorDetails(new Error('offline')), {
    statusCode: 502,
    statusMessage: '目前無法連線到 Bakery CMS。',
  });
});

test('fetchBakery normalizes the base URL and forwards the query', async () => {
  const result = await fetchBakery<{ ok: boolean }>(
    {} as H3Event,
    '/api/v2/pages/',
    { limit: '20' },
    {
      baseUrl: ' http://127.0.0.1:8000/ ',
      request: async (path, options) => {
        assert.equal(path, '/api/v2/pages/');
        assert.equal(options.baseURL, 'http://127.0.0.1:8000');
        assert.deepEqual(options.query, { limit: '20' });
        return { ok: true };
      },
    },
  );

  assert.deepEqual(result, { ok: true });
});

test('fetchBakery normalizes relative rendition URLs in API responses', async () => {
  const result = await fetchBakery<{
    rendition: {
      url: string;
      full_url?: string;
      width: number;
      height: number;
    };
  }>({} as H3Event, '/api/v2/pages/60/', undefined, {
    baseUrl: 'http://127.0.0.1:8000',
    request: async () => ({
      rendition: {
        url: '/media/images/hero.jpg',
        width: 1200,
        height: 675,
      },
    }),
  });

  assert.equal(
    result.rendition.full_url,
    'http://127.0.0.1:8000/media/images/hero.jpg',
  );
});

test('fetchBakery reports invalid config as 500 and upstream failures as 502', async () => {
  await assert.rejects(
    fetchBakery({} as H3Event, '/api/v2/pages/', undefined, {
      baseUrl: '',
      request: async () => ({}),
    }),
    (error: { statusCode?: number }) => error.statusCode === 500,
  );

  await assert.rejects(
    fetchBakery({} as H3Event, '/api/v2/pages/', undefined, {
      baseUrl: 'http://127.0.0.1:8000',
      request: async () => {
        throw new Error('offline');
      },
    }),
    (error: { statusCode?: number }) => error.statusCode === 502,
  );
});
