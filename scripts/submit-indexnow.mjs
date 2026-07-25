import { existsSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';
import { pingIndexNow } from './lib/indexnow.mjs';

const HOST = 'https://fish-point.pl';
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const ZERO_SHA = /^0+$/;

function gitNames(args) {
  const result = spawnSync('git', args, { cwd: ROOT, encoding: 'utf8' });
  return result.status === 0
    ? result.stdout.split('\n').map((line) => line.trim()).filter(Boolean)
    : [];
}

export function changedFiles(before = process.env.BEFORE_SHA, head = process.env.GITHUB_SHA || 'HEAD') {
  const committed = before && !ZERO_SHA.test(before)
    ? gitNames(['diff', '--name-only', before, head])
    : gitNames(['show', '--pretty=', '--name-only', head]);
  const generatedDuringBuild = gitNames(['diff', '--name-only']);
  return [...new Set([...committed, ...generatedDuringBuild])];
}

function isNoindex(relative) {
  const path = resolve(ROOT, relative);
  if (!existsSync(path)) return false;
  return /<meta\s+name=["']robots["'][^>]*content=["'][^"']*noindex/i.test(
    readFileSync(path, 'utf8'),
  );
}

function pageUrl(relative) {
  const normalized = relative.replaceAll('\\', '/').replace(/^\.\//, '');
  if (normalized === 'index.html') return `${HOST}/`;
  if (normalized.endsWith('/index.html')) {
    return `${HOST}/${normalized.slice(0, -'index.html'.length)}`;
  }
  return `${HOST}/${normalized}`;
}

export function urlsFromPaths(paths) {
  const urls = new Set();
  for (const raw of paths) {
    const relative = raw.replaceAll('\\', '/').replace(/^\.\//, '');
    if (!relative.endsWith('.html') || relative === '404.html' || isNoindex(relative)) continue;
    urls.add(pageUrl(relative));
    const slash = relative.indexOf('/');
    if (slash > 0) urls.add(`${HOST}/${relative.slice(0, slash)}/`);
    urls.add(`${HOST}/`);
  }
  return [...urls].sort();
}

async function waitForPublishedKey(keyUrl, attempts = 12) {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(`${keyUrl}?deploy=${Date.now()}`, { cache: 'no-store' });
      const body = (await response.text()).trim();
      const expected = keyUrl.split('/').at(-1).replace(/\.txt$/, '');
      if (response.ok && body === expected) return;
    } catch {
      // Railway may still be switching the production deployment.
    }
    if (attempt < attempts) await new Promise((resolveWait) => setTimeout(resolveWait, 5000));
  }
  throw new Error(`IndexNow key is not available at ${keyUrl}`);
}

async function main() {
  const dryRun = process.argv.includes('--dry-run');
  const separator = process.argv.indexOf('--files');
  const files = separator >= 0 ? process.argv.slice(separator + 1) : changedFiles();
  const urls = urlsFromPaths(files);
  console.log(`[indexnow] changed HTML URLs: ${urls.length}`);
  for (const url of urls) console.log(`[indexnow] ${url}`);
  if (dryRun || urls.length === 0) return;

  const key = process.env.INDEXNOW_KEY || 'a39db5495ae6e2738bab111816879bac94952af2c3003f3a11b16182cb7eb013';
  await waitForPublishedKey(`${HOST}/${key}.txt`);
  const status = await pingIndexNow(urls);
  if (status !== 200 && status !== 202) {
    throw new Error(`IndexNow submission failed with HTTP ${status ?? 'network error'}`);
  }
  console.log(`[indexnow] accepted with HTTP ${status}`);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(`[indexnow] ${error.message}`);
    process.exitCode = 1;
  });
}
