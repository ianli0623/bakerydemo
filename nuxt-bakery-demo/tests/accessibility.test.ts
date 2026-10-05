import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
  NodeTypes,
  type ElementNode,
  type RootNode,
  type TemplateChildNode,
} from '@vue/compiler-core';
import { parse } from '@vue/compiler-sfc';
import {
  getLanguageLinkLang,
  readStoredFontScale,
  reduceFontScale,
  writeStoredFontScale,
} from '../app/utils/accessibility.ts';

function findElementByClass(
  node: RootNode | TemplateChildNode,
  className: string,
): ElementNode | undefined {
  if (node.type === NodeTypes.ELEMENT) {
    const classAttribute = node.props.find(
      (property) =>
        property.type === NodeTypes.ATTRIBUTE && property.name === 'class',
    );
    if (classAttribute?.value?.content.split(/\s+/).includes(className)) {
      return node;
    }
  }

  if (!('children' in node)) return undefined;

  for (const child of node.children) {
    const match = findElementByClass(child, className);
    if (match) return match;
  }

  return undefined;
}

test('font scale controls clamp to three supported values', () => {
  assert.equal(reduceFontScale('default', 'increase'), 'large');
  assert.equal(reduceFontScale('large', 'increase'), 'large');
  assert.equal(reduceFontScale('default', 'decrease'), 'small');
  assert.equal(reduceFontScale('small', 'decrease'), 'small');
  assert.equal(reduceFontScale('small', 'reset'), 'default');
  assert.equal(reduceFontScale('large', 'reset'), 'default');
});

test('invalid or unavailable stored values fall back without throwing', () => {
  assert.equal(readStoredFontScale({ getItem: () => 'huge' }), 'default');
  assert.equal(readStoredFontScale({ getItem: () => 'large' }), 'large');
  assert.equal(
    readStoredFontScale({
      getItem: () => {
        throw new Error('blocked');
      },
    }),
    'default',
  );
  assert.doesNotThrow(() =>
    writeStoredFontScale(
      {
        setItem: () => {
          throw new Error('blocked');
        },
      },
      'large',
    ),
  );
});

test('language links declare only a language different from the current page', () => {
  assert.equal(getLanguageLinkLang('en', 'en'), undefined);
  assert.equal(getLanguageLinkLang('en', 'zh-tw'), 'zh-Hant');
  assert.equal(getLanguageLinkLang('zh-tw', 'zh-tw'), undefined);
  assert.equal(getLanguageLinkLang('zh-tw', 'en'), 'en');
});

test('homepage news stays in main content without a complementary landmark', () => {
  const source = readFileSync(
    new URL('../app/pages/index.vue', import.meta.url),
    'utf8',
  );
  const { descriptor, errors } = parse(source);

  assert.deepEqual(errors, []);
  assert.ok(descriptor.template);

  const newsContainer = findElementByClass(
    descriptor.template.ast,
    'home-news',
  );
  assert.ok(newsContainer);

  const roleAttribute = newsContainer.props.find(
    (property) =>
      property.type === NodeTypes.ATTRIBUTE && property.name === 'role',
  );
  const isComplementaryLandmark =
    newsContainer.tag === 'aside' ||
    roleAttribute?.value?.content === 'complementary';

  assert.equal(isComplementaryLandmark, false);
});
