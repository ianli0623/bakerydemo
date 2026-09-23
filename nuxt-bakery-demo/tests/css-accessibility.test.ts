import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { is } from 'css-select';
import { Element } from 'domhandler';
import postcss, { type Rule } from 'postcss';
import selectorParser from 'postcss-selector-parser';

const css = readFileSync(
  new URL('../app/assets/css/main.css', import.meta.url),
  'utf8',
);

type Specificity = [number, number, number];

function mediaMatches(rule: Rule, viewportWidth: number): boolean {
  let parent = rule.parent;

  while (parent) {
    if (parent.type === 'atrule' && parent.name === 'media') {
      const minWidth = parent.params.match(/min-width:\s*(\d+)px/);
      const maxWidth = parent.params.match(/max-width:\s*(\d+)px/);

      if (minWidth && viewportWidth < Number(minWidth[1])) return false;
      if (maxWidth && viewportWidth > Number(maxWidth[1])) return false;
    }
    parent = parent.parent;
  }

  return true;
}

function getSpecificity(selector: string): Specificity {
  const specificity: Specificity = [0, 0, 0];

  selectorParser((root) => {
    root.walk((node) => {
      if (node.type === 'id') specificity[0] += 1;
      if (
        node.type === 'class' ||
        node.type === 'attribute' ||
        node.type === 'pseudo'
      ) {
        specificity[1] += 1;
      }
      if (node.type === 'tag') specificity[2] += 1;
    });
  }).processSync(selector);

  return specificity;
}

function compareSpecificity(left: Specificity, right: Specificity): number {
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) return left[index] - right[index];
  }
  return 0;
}

function getSiteMapDisplay(locale: string, viewportWidth: number): string {
  const link = new Element('a', { class: 'nav-link nav-sitemap' }, []);
  const navigation = new Element('nav', { class: 'site-nav' }, [link]);
  const html = new Element('html', { lang: locale }, [navigation]);
  link.parent = navigation;
  navigation.parent = html;

  let display = '';
  let winningSpecificity: Specificity = [-1, -1, -1];
  let winningOrder = -1;
  let order = 0;

  postcss.parse(css).walkRules((rule) => {
    if (!mediaMatches(rule, viewportWidth)) return;
    if (
      !rule.nodes.some(
        (node) => node.type === 'decl' && node.prop === 'display',
      )
    ) {
      return;
    }

    for (const selector of rule.selectors) {
      if (selector.includes('::')) continue;
      const normalizedSelector = selector.replace(
        /:lang\(([^)]+)\)/g,
        '[lang="$1"]',
      );
      if (!is(link, normalizedSelector)) continue;

      const specificity = getSpecificity(selector);
      rule.walkDecls('display', (declaration) => {
        if (
          compareSpecificity(specificity, winningSpecificity) > 0 ||
          (compareSpecificity(specificity, winningSpecificity) === 0 &&
            order > winningOrder)
        ) {
          display = declaration.value;
          winningSpecificity = specificity;
          winningOrder = order;
        }
      });
    }
    order += 1;
  });

  return display;
}

function getCustomProperty(name: string): string {
  const match = css.match(
    new RegExp(`${name}:\\s*(#[0-9a-f]{3}(?:[0-9a-f]{3})?)`, 'i'),
  );

  assert.ok(match, `${name} must be defined as a hex color`);

  return match[1].length === 4
    ? `#${[...match[1].slice(1)].map((digit) => digit.repeat(2)).join('')}`
    : match[1];
}

function relativeLuminance(hex: string): number {
  const channels = hex
    .slice(1)
    .match(/.{2}/g)
    ?.map((channel) => Number.parseInt(channel, 16) / 255);

  assert.ok(channels);

  const [red, green, blue] = channels.map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
  );

  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrastRatio(foreground: string, background: string): number {
  const foregroundLuminance = relativeLuminance(foreground);
  const backgroundLuminance = relativeLuminance(background);
  const lighter = Math.max(foregroundLuminance, backgroundLuminance);
  const darker = Math.min(foregroundLuminance, backgroundLuminance);

  return (lighter + 0.05) / (darker + 0.05);
}

test('muted small text meets WCAG AA on every light site surface', () => {
  const muted = getCustomProperty('--color-muted');
  const lightSurfaces = [
    '--color-surface',
    '--color-sky',
    '--color-page',
    '--color-mint',
  ];

  for (const surface of lightSurfaces) {
    const ratio = contrastRatio(muted, getCustomProperty(surface));

    assert.ok(
      ratio >= 4.5,
      `${muted} on ${surface} has contrast ${ratio.toFixed(2)}:1; expected at least 4.5:1`,
    );
  }
});

test('site map stays out of the desktop primary navigation in every locale', () => {
  assert.equal(getSiteMapDisplay('en', 1200), 'none');
  assert.equal(getSiteMapDisplay('zh-tw', 1200), 'none');
  assert.equal(getSiteMapDisplay('en', 800), 'flex');
  assert.equal(getSiteMapDisplay('zh-tw', 800), 'flex');
});
