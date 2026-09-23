import { cpSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { dirname, extname, posix, resolve } from 'node:path';

const removableLinkRelations = new Set([
  'alternate',
  'canonical',
  'modulepreload',
  'prefetch',
  'preload',
]);

function readAttribute(tag, name) {
  return tag.match(new RegExp(`\\b${name}=["']([^"']*)["']`, 'i'))?.[1] ?? '';
}

function toExportTarget(pathname) {
  const path = pathname.replace(/^\/+/, '');
  if (!path) return 'index.html';
  if (extname(posix.basename(path))) return path;
  return `${path.replace(/\/+$/, '')}/index.html`;
}

export function toOfflineUrl(url, documentPath) {
  if (!url.startsWith('/') || url.startsWith('//')) return url;

  const [, pathname = '', suffix = ''] = url.match(/^([^?#]*)(.*)$/) ?? [];
  const target = toExportTarget(pathname);
  const fromDirectory = posix.dirname(documentPath.replaceAll('\\', '/'));
  return `${posix.relative(fromDirectory, target) || 'index.html'}${suffix}`;
}

export function rewriteOfflineDocument(html, documentPath) {
  let result = html.replace(/<script\b[\s\S]*?<\/script>/gi, '');

  result = result.replace(/<link\b[^>]*>/gi, (tag) => {
    const relations = readAttribute(tag, 'rel').toLowerCase().split(/\s+/);
    if (relations.some((relation) => removableLinkRelations.has(relation))) {
      return '';
    }
    return tag.replace(/\s+crossorigin(?:=(?:"[^"]*"|'[^']*'|[^\s>]+))?/gi, '');
  });

  result = result.replace(
    /\b(href|src)=(["'])([^"']*)\2/gi,
    (attribute, name, quote, url) =>
      `${name}=${quote}${toOfflineUrl(url, documentPath)}${quote}`,
  );

  const runtimePath = toOfflineUrl('/offline.js', documentPath);
  return result.replace(
    /<\/body>/i,
    `<script defer src="${runtimePath}"></script></body>`,
  );
}

export function createOfflineRootEntry() {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="0; url=en/index.html">
    <title>SEMI E187</title>
    <script>window.location.replace('en/index.html' + window.location.search + window.location.hash);</script>
  </head>
  <body>
    <p><a href="en/index.html">Continue to the SEMI E187 website</a></p>
  </body>
</html>
`;
}

export function replaceDirectoryContents(source, destination, allowedParent) {
  const sourcePath = resolve(source);
  const destinationPath = resolve(destination);
  const allowedParentPath = resolve(allowedParent);

  if (dirname(destinationPath) !== allowedParentPath) {
    throw new Error('靜態匯出目錄不在預期的 artifacts 資料夾內。');
  }
  if (sourcePath === destinationPath) {
    throw new Error('靜態來源與匯出目錄不可相同。');
  }

  mkdirSync(destinationPath, { recursive: true });
  for (const entry of readdirSync(destinationPath, { withFileTypes: true })) {
    rmSync(resolve(destinationPath, entry.name), {
      recursive: entry.isDirectory(),
      force: true,
      maxRetries: 5,
      retryDelay: 200,
    });
  }
  cpSync(sourcePath, destinationPath, { recursive: true });
}
