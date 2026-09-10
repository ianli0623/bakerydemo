import assert from 'node:assert/strict';
import test from 'node:test';
import {
  getLocalizedSeoLinks,
  getPageSeoPresentation,
} from '../shared/utils/localized-seo.ts';

test('localized SEO links expose a canonical URL and both language alternatives', () => {
  assert.deepEqual(
    getLocalizedSeoLinks('http://localhost:3100', 'en', 'resources'),
    {
      canonical: 'http://localhost:3100/en/resources/',
      alternatives: [
        {
          hreflang: 'zh-Hant',
          href: 'http://localhost:3100/zh-tw/resources/',
        },
        {
          hreflang: 'en',
          href: 'http://localhost:3100/en/resources/',
        },
        {
          hreflang: 'x-default',
          href: 'http://localhost:3100/en/resources/',
        },
      ],
    },
  );
});

test('page SEO uses localized CMS metadata and settings', () => {
  assert.deepEqual(
    getPageSeoPresentation(
      {
        title: 'Implementation Resources',
        seoTitle: 'SEMI E187 Implementation Resources',
        searchDescription: 'Official English implementation resources.',
        introduction: 'Fallback introduction.',
      },
      'SEMI E187',
    ),
    {
      title: 'SEMI E187 Implementation Resources',
      description: 'Official English implementation resources.',
    },
  );

  assert.deepEqual(
    getPageSeoPresentation(
      {
        title: 'Implementation Resources',
        seoTitle: '',
        searchDescription: '',
        introduction: 'Fallback introduction.',
      },
      'SEMI E187',
    ),
    {
      title: 'Implementation Resources | SEMI E187',
      description: 'Fallback introduction.',
    },
  );
});
