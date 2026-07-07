#!/usr/bin/env node
// Publikuje NAJŚWIEŻSZE, jeszcze nieopublikowane artykuły z aktualnosci/ jako
// posty na tablicy STRONY FishPoint na Facebooku (przeglądarka sterowana przez
// browser-harness, zalogowana jako strona). Sekwencja sprawdzona ręcznie:
// klik kompozytora -> klik pola -> wklej tekst -> Dalej -> Opublikuj.
// Pamięć opublikowanych: scripts/fb-promo/published-fb.json (slugi), więc ten
// sam wpis nie idzie dwa razy.
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { latestArticles } from '../lib/latest-articles.mjs';

const root = process.cwd();
const STATE = join(root, 'scripts', 'fb-promo', 'published-fb.json');
const SHOTS = join(root, 'obrazy', 'fb-posts');

const dryRun = process.argv.includes('--dry-run');
const countArg = process.argv.find(a => a.startsWith('--count='));
const count = Math.min(Number(countArg?.split('=')[1] || 3), 6);
// --all: wrzuć wszystkie nieopublikowane (do limitu 6), inaczej --count (domyślnie 3).
const all = process.argv.includes('--all');

function loadPublished() {
  try { return new Set(JSON.parse(readFileSync(STATE, 'utf8'))); }
  catch { return new Set(); }
}
function savePublished(set) {
  writeFileSync(STATE, JSON.stringify([...set], null, 2) + '\n');
}

const published = loadPublished();
const pool = latestArticles(root, 40).filter(a => {
  const file = a.url.split('/').filter(Boolean).pop();
  return existsSync(join(root, 'aktualnosci', file)) && !published.has(a.slug);
});
const selected = all ? pool.slice(0, 6) : pool.slice(0, count);

if (selected.length === 0) {
  console.log('[fb] Brak nowych, nieopublikowanych artykułów. Nic do wrzucenia.');
  process.exit(0);
}

// Tekst posta: zwięzły lead z tytułu + opis meta + link + hashtagi.
const plan = selected.map((a, i) => ({
  n: i + 1,
  slug: a.slug,
  url: a.url,
  text: `${a.title}\n\n${a.description}\n\n\u{1F449} ${a.url}\n\n#wędkarstwo #FishPoint`,
}));

if (dryRun) {
  console.log(JSON.stringify(plan, null, 2));
  process.exit(0);
}

if (!existsSync(SHOTS)) mkdirSync(SHOTS, { recursive: true });

// Współrzędne kompozytora strony (viewport harnessa 1920x909, bez chrome).
const py = String.raw`
import time
items = __ITEMS__
SHOTS = "__SHOTS__"

def shot(name):
    try:
        p = SHOTS + "/" + name + ".png"
        capture_screenshot(p)
        return p
    except Exception as e:
        print("[fb] screenshot err:", e); return ""

def bottom_button():
    # Znajdź dolny przycisk dialogu: „Opublikuj" (priorytet) albo „Dalej".
    return js(r'''(() => {
      const dlgs = document.querySelectorAll('div[role="dialog"]');
      const scope = dlgs[dlgs.length-1] || document;
      const btns = Array.from(scope.querySelectorAll('[role="button"], button'));
      for (const label of ['Opublikuj','Dalej']){
        for (const e of btns){
          const txt=(e.innerText||e.textContent||'').trim();
          const a=e.getAttribute('aria-label')||'';
          const dis=e.getAttribute('aria-disabled')==='true'||e.disabled;
          const r=e.getBoundingClientRect();
          if(!dis && r.width>40 && r.height>20 && (txt===label||a===label)) return [r.x+r.width/2, r.y+r.height/2, label];
        }
      }
      return null;
    })()''')

def post_one(idx, item):
    # Świeża karta FB (uaktywnia ją) — wszystko dzieje się na niej.
    new_tab('https://www.facebook.com/')
    wait_for_load(); time.sleep(9)
    click_at_xy(910.0, 103.0)          # kompozytor „O czym myślisz…"
    time.sleep(6)
    click_at_xy(863.0, 390.0)          # pole tekstowe
    time.sleep(1)
    type_text(item['text'])
    time.sleep(11)                     # podglad linku (obraz OG)
    shot('wpisano-%d' % idx)
    # Dalej -> Opublikuj (dolny przycisk; szukamy po tekście, klikamy wsp.)
    published = False
    for step in range(8):
        b = bottom_button()
        if b:
            click_at_xy(float(b[0]), float(b[1]))
            print('[fb] %d klik: %s' % (idx, b[2]))
            time.sleep(5)
            if b[2] == 'Opublikuj':
                published = True
                break
        else:
            time.sleep(2)
    time.sleep(8)                      # dokoncz publikowanie
    p = shot('opublikowano-%d' % idx)
    print('[fb] %d slug=%s published=%s shot=%s' % (idx, item['slug'], published, p))
    if published:
        print('PUBLISHED ' + item['slug'])
    try: close_tab()
    except Exception: pass

for i, it in enumerate(items, 1):
    print('[fb] === %d/%d: %s ===' % (i, len(items), it['slug']))
    try:
        post_one(i, it)
    except Exception as e:
        print('[fb] %d blad: %s' % (i, e))
    time.sleep(4)
print('[fb] KONIEC')
`;

const out = spawnSync('browser-harness', [], {
  input: py.replace('__ITEMS__', JSON.stringify(plan)).replace('__SHOTS__', SHOTS),
  encoding: 'utf8', stdio: ['pipe', 'pipe', 'inherit'],
});
const stdout = out.stdout || '';
process.stdout.write(stdout);

// Zapisz jako opublikowane te, które skrypt potwierdził linią „PUBLISHED <slug>".
const okSlugs = [...stdout.matchAll(/^PUBLISHED (.+)$/gm)].map(m => m[1].trim());
for (const s of okSlugs) published.add(s);
savePublished(published);
console.log(`[fb] Zapisano jako opublikowane: ${okSlugs.length} (łącznie w pamięci: ${published.size}).`);
