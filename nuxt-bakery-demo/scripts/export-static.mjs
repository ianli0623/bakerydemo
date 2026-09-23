import { spawnSync } from 'node:child_process';
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { dirname, extname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  createOfflineRootEntry,
  replaceDirectoryContents,
  rewriteOfflineDocument,
} from './offline-site.mjs';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const workspaceRoot = resolve(projectRoot, '..');
const generatedRoot = resolve(projectRoot, '.output', 'public');
const artifactsRoot = resolve(workspaceRoot, 'artifacts');
const exportRoot = resolve(artifactsRoot, 'semi-e187-static-site');
const nuxtCli = resolve(projectRoot, 'node_modules', 'nuxt', 'bin', 'nuxt.mjs');
const offlineRuntimeSource = resolve(
  projectRoot,
  'scripts',
  'offline-runtime.js',
);

const localizedSlugs = [
  '',
  'about',
  'resources',
  'certification',
  'ecosystem',
  'sitemap',
  'compliance-registry',
];
const expectedHtmlFiles = [
  'index.html',
  ...['en', 'zh-tw'].flatMap((locale) =>
    localizedSlugs.map((slug) =>
      slug ? `${locale}/${slug}/index.html` : `${locale}/index.html`,
    ),
  ),
];
const searchableExtensions = new Set(['.css', '.html', '.js', '.json', '.mjs']);

function readConfiguredBaseUrl() {
  if (process.env.NUXT_BAKERY_BASE_URL) {
    return process.env.NUXT_BAKERY_BASE_URL.replace(/\/+$/, '');
  }

  const envPath = resolve(projectRoot, '.env');
  if (!existsSync(envPath)) {
    throw new Error('找不到 nuxt-bakery-demo/.env。');
  }

  const match = readFileSync(envPath, 'utf8').match(
    /^NUXT_BAKERY_BASE_URL\s*=\s*["']?([^\r\n"']+)["']?\s*$/m,
  );
  if (!match?.[1]) {
    throw new Error('尚未設定 NUXT_BAKERY_BASE_URL。');
  }

  return match[1].trim().replace(/\/+$/, '');
}

function walkFiles(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(root, entry.name);
    return entry.isDirectory() ? walkFiles(path) : [path];
  });
}

function prepareExportDirectory() {
  mkdirSync(artifactsRoot, { recursive: true });
  replaceDirectoryContents(generatedRoot, exportRoot, artifactsRoot);
}

function ensureRootEntryPage() {
  const rootIndex = resolve(exportRoot, 'index.html');
  writeFileSync(rootIndex, createOfflineRootEntry(), 'utf8');
}

function convertHtmlDocumentsToOffline() {
  for (const file of walkFiles(exportRoot)) {
    if (extname(file) !== '.html') continue;
    const documentPath = relative(exportRoot, file).replaceAll('\\', '/');
    writeFileSync(
      file,
      rewriteOfflineDocument(readFileSync(file, 'utf8'), documentPath),
      'utf8',
    );
  }
}

function copyOfflineRuntime() {
  writeFileSync(
    resolve(exportRoot, 'offline.js'),
    readFileSync(offlineRuntimeSource),
  );
}

function normalizeMediaReferences(baseUrl) {
  const absoluteMediaPrefix = `${baseUrl}/media/`;
  const mediaPaths = new Set();

  for (const file of walkFiles(exportRoot)) {
    if (!searchableExtensions.has(extname(file))) continue;

    const original = readFileSync(file, 'utf8');
    const normalized = original.split(absoluteMediaPrefix).join('/media/');
    if (normalized !== original) writeFileSync(file, normalized);

    for (const match of normalized.matchAll(/\/media\/[^"'\\\s<>()]+/g)) {
      mediaPaths.add(match[0].replace(/&amp;/g, '&'));
    }
  }

  return [...mediaPaths].sort();
}

async function downloadMediaFiles(baseUrl, mediaPaths) {
  for (const mediaPath of mediaPaths) {
    const response = await fetch(new URL(mediaPath, `${baseUrl}/`));
    if (!response.ok) {
      throw new Error(`無法下載媒體檔案 ${mediaPath}：HTTP ${response.status}`);
    }

    const destination = resolve(exportRoot, mediaPath.replace(/^\/+/, ''));
    mkdirSync(dirname(destination), { recursive: true });
    writeFileSync(destination, Buffer.from(await response.arrayBuffer()));
  }
}

function validateExport() {
  const missing = expectedHtmlFiles.filter(
    (file) => !existsSync(resolve(exportRoot, file)),
  );
  const cssFiles = walkFiles(exportRoot).filter(
    (file) => extname(file) === '.css' && statSync(file).size > 0,
  );

  if (missing.length > 0) {
    throw new Error(`靜態匯出缺少頁面：\n${missing.join('\n')}`);
  }
  if (cssFiles.length === 0) {
    throw new Error('靜態匯出沒有 CSS 檔案。');
  }

  for (const file of walkFiles(exportRoot).filter(
    (candidate) => extname(candidate) === '.html',
  )) {
    const contents = readFileSync(file, 'utf8');
    if (/\b(?:href|src)=["']\/(?!\/)/i.test(contents)) {
      throw new Error(
        `離線頁面仍包含網站根目錄路徑：${relative(exportRoot, file)}`,
      );
    }
    if (/type=["']module["']|data-nuxt-data|window\.__NUXT__/i.test(contents)) {
      throw new Error(
        `離線頁面仍包含需要網站伺服器的 Nuxt 程式：${relative(exportRoot, file)}`,
      );
    }
  }

  if (!existsSync(resolve(exportRoot, 'offline.js'))) {
    throw new Error('靜態匯出缺少離線互動程式 offline.js。');
  }
}

function writeInstructions(mediaCount) {
  const instructions = `SEMI E187 純靜態前台

使用方式：直接雙擊本資料夾內的 index.html，即可用瀏覽器離線瀏覽。
不需要安裝 Nginx、IIS、Node.js、Python 或資料庫。
請保留資料夾結構，不要單獨移動 HTML、CSS、JavaScript 或圖片檔案。
內容：英文版、繁體中文版、網站導覽、線上合規名冊、CSS、JavaScript 與 ${mediaCount} 個媒體檔案。
注意：這是匯出當下的內容快照，後台修改後需重新執行 npm run export:static。
`;
  writeFileSync(resolve(exportRoot, 'README.txt'), instructions, 'utf8');
}

async function main() {
  const baseUrl = readConfiguredBaseUrl();
  const result = spawnSync(process.execPath, [nuxtCli, 'generate'], {
    cwd: projectRoot,
    env: {
      ...process.env,
      NUXT_BAKERY_BASE_URL: baseUrl,
      NUXT_STATIC_EXPORT: 'true',
    },
    stdio: 'inherit',
  });

  if (result.status !== 0 || !existsSync(generatedRoot)) {
    throw new Error('前台靜態產生失敗，未建立 .output/public。');
  }

  prepareExportDirectory();
  const mediaPaths = normalizeMediaReferences(baseUrl);
  await downloadMediaFiles(baseUrl, mediaPaths);
  convertHtmlDocumentsToOffline();
  ensureRootEntryPage();
  copyOfflineRuntime();
  validateExport();
  writeInstructions(mediaPaths.length);

  console.log(`\n靜態網站已匯出至：${exportRoot}`);
  console.log(`HTML 頁面：${expectedHtmlFiles.length}`);
  console.log(`媒體檔案：${mediaPaths.length}`);
}

await main();
