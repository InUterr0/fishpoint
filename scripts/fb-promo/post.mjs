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

def click_button(labels):
    # Szuka WIDOCZNEGO, aktywnego przycisku o danym tekście w DOWOLNYM dialogu
    # (FB miewa 2 nakładające się dialogi) i klika go realną sekwencją zdarzeń
    # myszy — sam click_at_xy bywa ignorowany przez handlery Reacta FB.
    # labels: lista etykiet wg priorytetu, np. ['Opublikuj','Dalej'].
    payload = js(r'''(() => {
      const want = __LABELS__;
      const all = Array.from(document.querySelectorAll('[role="button"], button'));
      for (const label of want){
        let best=null;
        for (const e of all){
          const txt=(e.innerText||e.textContent||'').trim();
          const a=e.getAttribute('aria-label')||'';
          if(txt!==label && a!==label) continue;
          if(e.getAttribute('aria-disabled')==='true'||e.disabled) continue;
          const r=e.getBoundingClientRect();
          if(r.width<60||r.height<20||r.y<0||r.y>909) continue;
          if(!e.closest('div[role="dialog"]')) continue;
          if(!best||r.width>best.w) best={el:e,x:r.x+r.width/2,y:r.y+r.height/2,w:r.width};
        }
        if(best){
          const el=best.el,x=best.x,y=best.y;
          for(const t of ['pointerover','pointerdown','mousedown','pointerup','mouseup','click'])
            el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,clientX:x,clientY:y,button:0}));
          return label;
        }
      }
      return '';
    })()'''.replace('__LABELS__', __import__('json').dumps(labels)))
    return (payload or '').strip().strip('"')

def composer_open():
    # Czy w dialogu wciąż jest widoczny przycisk Dalej/Opublikuj (kompozytor żyje)?
    return js(r'''(() => {
      const all=Array.from(document.querySelectorAll('[role="button"]'));
      for(const e of all){const t=(e.innerText||e.textContent||'').trim();const a=e.getAttribute('aria-label')||'';
        if((/^(Dalej|Opublikuj)$/.test(t)||/^(Dalej|Opublikuj)$/.test(a))&&e.closest('div[role="dialog"]')){
          const r=e.getBoundingClientRect(); if(r.width>60&&r.y>=0&&r.y<=909) return '1';}}
      return '0';
    })()''').strip().strip('"') == '1'

def post_one(idx, item):
    # Świeża karta FB (uaktywnia ją) — wszystko dzieje się na niej.
    new_tab('https://www.facebook.com/')
    wait_for_load(); time.sleep(9)
    click_at_xy(910.0, 103.0)          # kompozytor „O czym myślisz…"
    time.sleep(6)
    click_at_xy(863.0, 390.0)          # pole tekstowe
    time.sleep(1)
    type_text(item['text'])
    time.sleep(12)                     # podglad linku (obraz OG)
    shot('wpisano-%d' % idx)
    # Klikaj „Dalej" aż pojawi się „Opublikuj", potem kliknij „Opublikuj” DOKŁADNIE
    # RAZ (powtarzanie grozi duplikatami na wolniejszym łączu) i zweryfikuj wynik.
    published = False
    for step in range(12):
        clicked = click_button(['Opublikuj', 'Dalej'])
        if clicked == 'Opublikuj':
            print('[fb] %d klik: Opublikuj' % idx)
            time.sleep(9)                       # FB kończy publikowanie
            published = not composer_open()      # dialog zniknął => opublikowano
            break                                # nigdy nie klikaj Opublikuj drugi raz
        elif clicked == 'Dalej':
            print('[fb] %d klik: Dalej' % idx)
            time.sleep(5)
        else:
            time.sleep(2)
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
