#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { latestArticles } from '../lib/latest-articles.mjs';
import { pingIndexNow } from '../lib/indexnow.mjs';

const root = process.cwd();
// Artykuły brane na żywo z aktualnosci/ (od najświeższych), więc plan promo
// zawsze dotyczy aktualnych wpisów. Użyj --latest=N, by poszerzyć pulę.
const latestArg = process.argv.find(a => a.startsWith('--latest='));
const poolSize = Number(latestArg?.split('=')[1] || 10);
const articles = latestArticles(root, poolSize);

const dryRun = process.argv.includes('--dry-run');
const manual = process.argv.includes('--manual');
const countArg = process.argv.find(a => a.startsWith('--count='));
const delayArg = process.argv.find(a => a.startsWith('--delay-ms='));
// Default is intentionally conservative: fewer high-fit comments are safer and look less spammy.
const count = Math.min(Number(countArg?.split('=')[1] || 3), 5);
const delayMs = Number(delayArg?.split('=')[1] || 90000);

function sh(cmd, input) {
  const r = spawnSync('bash', ['-lc', cmd], { input, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
  if (r.status !== 0) throw new Error(`${cmd}\n${r.stderr || r.stdout}`);
  return r.stdout;
}

function articleExists(url) {
  // URL kończy się na <slug>.html, więc nazwa pliku to ostatni segment as-is.
  const file = url.split('/').filter(Boolean).pop();
  return existsSync(join(root, 'aktualnosci', file));
}

// --skip=N drops the N freshest articles — useful to retry a partially
// failed run without double-posting the items that already went out.
const skipArg = process.argv.find(a => a.startsWith('--skip='));
const skip = Math.max(0, Number(skipArg?.split('=')[1] || 0));
const selected = articles.filter(a => articleExists(a.url)).slice(skip, skip + count);
if (selected.length === 0) throw new Error('No matching article files found. Run from project root.');

const plan = selected.map((a, i) => ({
  n: i + 1,
  search: `https://x.com/search?q=${encodeURIComponent(a.query)}&src=typed_query&f=live`,
  comment: `${a.note}\n\nWięcej: ${a.url}`
}));

if (dryRun) {
  console.log(JSON.stringify(plan, null, 2));
  process.exit(0);
}

const py = String.raw`
import time
items = __ITEMS__
manual = __MANUAL__

def shot(label=''):
    try:
        p = capture_screenshot()
        print(f'[x-promo] screenshot {label}: {p}')
    except Exception as e:
        print(f'[x-promo] screenshot failed: {e}')

def dismiss_unlock_modal():
    # X sometimes shows "Unlock more on X" after a successful post. Close/ack it if visible.
    try:
        txt = js("document.body.innerText") or ""
        if 'Unlock more on X' in txt or 'Your post was sent' in txt:
            click_at_xy(960, 728)  # Got it button area on the modal
            time.sleep(1)
            return True
    except Exception:
        pass
    return False

def visible_text():
    try:
        return js("document.body.innerText") or ""
    except Exception:
        return ""

def center_of_reply_icon():
    return js(r'''(() => {
      const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
      const candidates = buttons.map((e) => {
        const a = e.getAttribute('aria-label') || '';
        const r = e.getBoundingClientRect();
        return {a, x:r.x, y:r.y, w:r.width, h:r.height};
      }).filter(b => /reply/i.test(b.a) && b.x > 560 && b.x < 1220 && b.y > 250 && b.y < 850 && b.w > 10 && b.h > 10)
        .sort((a,b) => a.y - b.y);
      if (!candidates.length) return null;
      const b = candidates[0];
      return [b.x + b.w/2, b.y + b.h/2, b.a];
    })()''')

def center_of_button_text(label):
    return js(r'''((label) => {
      const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
      const candidates = buttons.map((e) => {
        const txt = (e.innerText || e.textContent || '').trim();
        const a = e.getAttribute('aria-label') || '';
        const r = e.getBoundingClientRect();
        return {txt, a, x:r.x, y:r.y, w:r.width, h:r.height, disabled:e.disabled || e.getAttribute('aria-disabled') === 'true'};
      }).filter(b => !b.disabled && (b.txt === label || b.a === label) && b.w > 10 && b.h > 10)
        .sort((a,b) => b.y - a.y);
      if (!candidates.length) return null;
      const b = candidates[0];
      return [b.x + b.w/2, b.y + b.h/2, b.txt || b.a];
    })(''' + repr(label) + r''')''')

def click_center(pos, fallback_x=None, fallback_y=None):
    if pos and isinstance(pos, list) and len(pos) >= 2:
        click_at_xy(float(pos[0]), float(pos[1]))
        return True
    if fallback_x is not None:
        click_at_xy(fallback_x, fallback_y)
        return True
    return False

def post_reply(comment):
    # One attempt per item: click reply, type immediately (X auto-focuses the
    # composer), submit with Ctrl+Enter, verify. If anything is off — skip.
    opened = js(r'''(() => {
      const btn = document.querySelector('article [data-testid="reply"]');
      if (!btn) return 'no-reply-button';
      btn.scrollIntoView({block: 'center'});
      btn.click();
      return 'clicked';
    })()''')
    print(f'[x-promo] reply click: {opened}')
    if opened != 'clicked':
        return False
    time.sleep(5)
    txt = visible_text()
    if 'Unlock more on X' in txt:
        print('[x-promo] X limit modal; skipping item')
        dismiss_unlock_modal()
        return False
    # Type blind — the composer grabs focus on open; verify the text landed.
    type_text(comment)
    time.sleep(1.5)
    if comment[:40] not in visible_text():
        print('[x-promo] typed text not visible — composer never took focus; skipping')
        shot('no-composer')
        return False
    press_key('Enter', modifiers=2)
    time.sleep(4)
    txt = visible_text()
    if 'Your post was sent' in txt or 'Unlock more on X' in txt:
        print('[x-promo] posted')
        dismiss_unlock_modal()
        return True
    if comment[:40] not in txt and 'Save post?' not in txt:
        print('[x-promo] composer closed after submit; treating as posted')
        return True
    print('[x-promo] could not verify sent state; skipping')
    shot('unverified')
    return False

posted = 0
for idx, item in enumerate(items, 1):
    new_tab(item['search'])
    wait_for_load()
    time.sleep(5)
    print(f'[x-promo] target {idx}: {item["search"]}')
    print(f'[x-promo] comment: {item["comment"]}')
    if manual:
        print('[x-promo] manual mode: opened search and printed comment only')
    else:
        ok = post_reply(item['comment'])
        if ok:
            posted += 1
        else:
            print('[x-promo] failed/skipped one item; continuing cautiously')
    try:
        close_tab()
    except Exception as e:
        print(f'[x-promo] close_tab failed: {e}')
    if idx < len(items):
        time.sleep(__DELAY__ / 1000)
print(f'[x-promo] done; posted={posted}; planned={len(items)}; manual={manual}')
`;

const out = sh('browser-harness', py
  .replace('__ITEMS__', JSON.stringify(plan))
  .replace('__DELAY__', String(delayMs))
  .replace('__MANUAL__', manual ? 'True' : 'False'));
process.stdout.write(out);

// Dodatkowy ping IndexNow dla promowanych artykułów (nie blokuje, nie wywala runu).
const inStatus = await pingIndexNow(selected.map(a => a.url));
if (inStatus) console.log(`[x-promo] indexnow: HTTP ${inStatus}`);
