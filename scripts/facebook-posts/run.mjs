#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { latestArticles } from '../lib/latest-articles.mjs';
import { FB } from '../lib/fb-config.mjs';
import { pingIndexNow } from '../lib/indexnow.mjs';

// Posts are built live from the freshest published articles (featured first).
// Use --latest=N to widen the candidate pool.
const latestArg = process.argv.find(a => a.startsWith('--latest='));
const poolSize = Number(latestArg?.split('=')[1] || 8);
const articles = latestArticles(process.cwd(), poolSize);
const posts = articles.map(a => `${a.description}\n\nCzytaj: ${a.url}`);
const dryRun = process.argv.includes('--dry-run');
const countArg = process.argv.find(a => a.startsWith('--count='));
const delayArg = process.argv.find(a => a.startsWith('--delay-ms='));
const count = Math.min(Number(countArg?.split('=')[1] || 2), 4);
const delayMs = Number(delayArg?.split('=')[1] || 90000);
const assetId = FB.ASSET_ID;

const selected = posts.slice(0, count);
if (dryRun) {
  console.log(JSON.stringify(selected.map((text, i) => ({ n: i + 1, text })), null, 2));
  process.exit(0);
}

function runHarness(code) {
  const r = spawnSync('bash', ['-lc', 'browser-harness'], { input: code, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
  if (r.status !== 0) throw new Error(r.stderr || r.stdout);
  process.stdout.write(r.stdout);
}

const py = String.raw`
import time, json
posts = __POSTS__
asset_id = __ASSET_ID__
delay_ms = __DELAY_MS__

def body_text():
    try:
        return js('document.body.innerText') or ''
    except Exception:
        return ''

def post_once(text, idx):
    new_tab(f'https://business.facebook.com/latest/composer?asset_id={asset_id}')
    wait_for_load()
    time.sleep(6)
    selector='div[aria-label="Napisz w oknie dialogowym, aby dołączyć tekst do posta."]'
    ok = js(f"!!document.querySelector({selector!r})")
    if not ok:
        print(f'[fejs-posty] composer text box not found for post {idx}')
        print(capture_screenshot())
        return False
    js(f"document.querySelector({selector!r}).focus()")
    type_text(text)
    time.sleep(6)
    # Meta Business Suite publish button in current PL UI.
    pos = js(r'''(()=>{const bs=Array.from(document.querySelectorAll('div[role="button"],button')).map(e=>{const r=e.getBoundingClientRect();return {t:(e.innerText||'').trim(),a:e.getAttribute('aria-label')||'',x:r.x,y:r.y,w:r.width,h:r.height,dis:e.getAttribute('aria-disabled')==='true'||e.disabled}}).filter(b=>!b.dis && (b.t==='Opublikuj'||b.t==='Post'||b.a==='Opublikuj'||b.a==='Post') && b.w>20&&b.h>20).sort((a,b)=>b.y-a.y); if(!bs.length)return null; const b=bs[0]; return [b.x+b.w/2,b.y+b.h/2,b.t||b.a];})()''')
    print(f'[fejs-posty] publish target post {idx}: {pos}')
    if pos:
        click_at_xy(float(pos[0]), float(pos[1]))
    else:
        click_at_xy(620,856)
    time.sleep(12)
    txt = body_text()
    if 'Post został opublikowany' in txt or 'Your post was published' in txt:
        print(f'[fejs-posty] published post {idx}')
        try:
            click_at_xy(642,759)  # close success/promo modal if visible
            time.sleep(2)
        except Exception:
            pass
        return True
    # The success toast often disappears before we read it — fall back to
    # checking the content calendar (Terminarz) for the post's opening text.
    print(f'[fejs-posty] toast missed for post {idx}; checking content calendar')
    new_tab(f'https://business.facebook.com/latest/content_calendar?asset_id={asset_id}')
    wait_for_load()
    time.sleep(8)
    found = text[:45] in body_text()
    print(capture_screenshot())
    try:
        close_tab()
    except Exception:
        pass
    if found:
        print(f'[fejs-posty] published post {idx} (verified in calendar)')
        return True
    print(f'[fejs-posty] not verified post {idx}')
    return False

published = 0
for i, p in enumerate(posts, 1):
    if post_once(p, i):
        published += 1
    try:
        close_tab()  # composer tab for this item
    except Exception:
        pass
    if i < len(posts):
        time.sleep(delay_ms/1000)
print(f'[fejs-posty] done published={published} planned={len(posts)}')
`;

runHarness(py
  .replace('__POSTS__', JSON.stringify(selected))
  .replace('__ASSET_ID__', JSON.stringify(assetId))
  .replace('__DELAY_MS__', String(delayMs)));

// Dodatkowy ping IndexNow dla promowanych artykułów (nie blokuje, nie wywala runu).
const status = await pingIndexNow(articles.slice(0, count).map(a => a.url));
if (status) console.log(`[fejs-posty] indexnow: HTTP ${status}`);
