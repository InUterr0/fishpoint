#!/usr/bin/env node
// Publikuje najnowsze artykuły FishPoint jako posty na tablicy STRONY na Facebooku
// (przeglądarka sterowana przez browser-harness musi być zalogowana jako strona).
// Wpisuje tekst + link w kompozytor „O czym myślisz, FishPoint?" i klika „Opublikuj";
// Facebook sam dociąga podgląd linku. Bez API, po prostu z zalogowanej karty.
import { spawnSync } from 'node:child_process';
import { latestArticles } from '../lib/latest-articles.mjs';

const root = process.cwd();
const dryRun = process.argv.includes('--dry-run');
const countArg = process.argv.find(a => a.startsWith('--count='));
const delayArg = process.argv.find(a => a.startsWith('--delay-ms='));
const count = Math.min(Number(countArg?.split('=')[1] || 3), 6);
const delayMs = Number(delayArg?.split('=')[1] || 45000);
// Pozwól wskazać konkretne slugi (argumenty bez „--"); inaczej N najnowszych.
const slugArgs = process.argv.slice(2).filter(a => !a.startsWith('--'));

// Ręcznie dopracowane, „ludzkie" teksty postów dla świeżych wpisów.
// Fallback (inne slugi): tytuł + opis meta + link.
const HAND = {
  'zezwolenia-online-2026':
    '📱 Koniec papierowych zezwoleń! Od 2026 roku pozwolenie na połów kupujesz i okazujesz już tylko cyfrowo — jako PDF z kodem QR w telefonie.\n\nCo to znaczy dla ~1,5 mln wędkarzy, jak działa nowy system i o czym pamiętać nad wodą (naładowany telefon to podstawa 😉) — rozkładamy na czynniki pierwsze:',
  'zlota-alga-lato-2026':
    '⚠️ Złota alga znów daje o sobie znać. Latem 2026 służby ponownie odnotowały lokalne śnięcia ryb na Odrze i wzmocniły monitoring.\n\nCzym właściwie jest ten glon, dlaczego wraca co roku i — najważniejsze — jak powinien zareagować wędkarz, gdy zobaczy śnięte ryby? Bez paniki, ale i bez bagatelizowania:',
  'gorne-wymiary-ochronne-2026':
    '🎣 „Za duża — też wypuść?" Coraz więcej wód wprowadza górny wymiar ochronny i tzw. okno łowne: zabrać wolno tylko rybę ze środkowego przedziału, a największe okazy wracają do wody.\n\nPo co chroni się duże tarlaki, jak czytać taki przepis i gdzie sprawdzić zasady dla swojej wody:',
};

const pool = latestArticles(root, 30);
let selected;
if (slugArgs.length) {
  selected = slugArgs.map(s => pool.find(a => a.slug === s)).filter(Boolean);
} else {
  selected = pool.slice(0, count);
}
if (!selected.length) throw new Error('Brak pasujących artykułów. Uruchom z katalogu głównego projektu.');

const plan = selected.map((a, i) => ({
  n: i + 1,
  slug: a.slug,
  url: a.url,
  text: (HAND[a.slug] || `${a.title}\n\n${a.description}`) + `\n\n👉 ${a.url}\n\n#wędkarstwo #FishPoint`,
}));

if (dryRun) {
  console.log(JSON.stringify(plan, null, 2));
  process.exit(0);
}

const py = String.raw`
import time, json
items = __ITEMS__

def shot(label=''):
    try:
        p = capture_screenshot()
        print(f'[fb] screenshot {label}: {p}')
    except Exception as e:
        print(f'[fb] screenshot failed: {e}')

def vtext():
    try:
        return js("document.body.innerText") or ""
    except Exception:
        return ""

def dialog_open():
    return js(r'''(() => !!document.querySelector('div[role="dialog"] [contenteditable="true"]'))''')

def open_composer():
    # Znajdź prostokąt pola „O czym myślisz…" i kliknij REALNYM kliknięciem myszy
    # (JS .click() nie odpala handlerów React FB).
    pos = js(r'''(() => {
      const els = Array.from(document.querySelectorAll('div, span, [role="button"]'));
      const t = els.find(e => /O czym myślisz/i.test((e.innerText||'')) && (e.innerText||'').length < 60);
      if (!t) return null;
      const r = t.getBoundingClientRect();
      return [r.x + r.width/2, r.y + r.height/2];
    })()''')
    if not (pos and isinstance(pos, list)):
        return 'no-trigger'
    click_at_xy(float(pos[0]), float(pos[1]))
    time.sleep(3)
    if dialog_open():
        return 'clicked'
    # druga próba
    click_at_xy(float(pos[0]), float(pos[1]))
    time.sleep(3)
    return 'clicked' if dialog_open() else 'no-dialog'

def editable_text():
    return js(r'''(() => { const b=document.querySelector('div[role="dialog"] [contenteditable="true"]'); return b ? (b.innerText||'') : ''; })()''')

def find_editable_and_type(text):
    pos = js(r'''(() => {
      const box = document.querySelector('div[role="dialog"] [contenteditable="true"]');
      if (!box) return null;
      const r = box.getBoundingClientRect();
      return [r.x + Math.min(60, r.width/2), r.y + Math.min(24, r.height/2)];
    })()''')
    if pos and isinstance(pos, list):
        click_at_xy(float(pos[0]), float(pos[1]))
        time.sleep(0.8)
    type_text(text)
    return True

def click_publish():
    pos = js(r'''(() => {
      const scope = document.querySelector('div[role="dialog"]') || document;
      const btns = Array.from(scope.querySelectorAll('[role="button"], button'));
      const cand = btns.map(e => {
        const txt = (e.innerText||e.textContent||'').trim();
        const a = e.getAttribute('aria-label')||'';
        const r = e.getBoundingClientRect();
        const dis = e.getAttribute('aria-disabled')==='true' || e.disabled;
        return {txt,a,x:r.x,y:r.y,w:r.width,h:r.height,dis};
      }).filter(b => !b.dis && b.w>20 && b.h>15 &&
                     (b.txt==='Opublikuj' || b.a==='Opublikuj' || b.txt==='Publish' || b.a==='Publish'));
      if (!cand.length) return null;
      const b = cand[0];
      return [b.x + b.w/2, b.y + b.h/2];
    })()''')
    if pos and isinstance(pos, list):
        click_at_xy(float(pos[0]), float(pos[1]))
        return True
    return False

def post_one(idx, item):
    new_tab('https://www.facebook.com/')
    wait_for_load(); time.sleep(6)
    o = open_composer()
    print(f'[fb] {idx} composer: {o}')
    if o != 'clicked':
        shot(f'no-composer-{idx}');
        try: close_tab()
        except Exception: pass
        return False
    time.sleep(2)
    find_editable_and_type(item['text'])
    time.sleep(2.5)
    if item['text'][:20] not in editable_text():
        print(f'[fb] {idx} tekst nie wszedł do kompozytora — pomijam')
        shot(f'no-text-{idx}')
        try: close_tab()
        except Exception: pass
        return False
    # daj chwilę na dociągnięcie podglądu linku
    time.sleep(7)
    ok = click_publish()
    print(f'[fb] {idx} publish click: {ok}')
    time.sleep(7)
    shot(f'after-publish-{idx}')
    # heurystyka sukcesu: kompozytor zamknięty (brak przycisku Opublikuj / dialogu)
    still = js(r'''(() => !!document.querySelector('div[role="dialog"] [contenteditable="true"]'))''')
    posted = (ok and not still)
    print(f'[fb] {idx} dialog_still_open={still} -> posted={posted}')
    try: close_tab()
    except Exception as e: print(f'[fb] close_tab: {e}')
    return posted

done = 0
for idx, item in enumerate(items, 1):
    print(f'[fb] === {idx}/{len(items)}: {item["slug"]} ===')
    try:
        if post_one(idx, item):
            done += 1
    except Exception as e:
        print(f'[fb] {idx} błąd: {e}')
    if idx < len(items):
        time.sleep(__DELAY__ / 1000)
print(f'[fb] DONE done={done} planned={len(items)}')
`;

function sh(cmd, input) {
  const r = spawnSync(cmd, [], { input, encoding: 'utf8', stdio: ['pipe', 'pipe', 'inherit'], shell: false });
  return r.stdout || '';
}

const out = sh('browser-harness', py
  .replace('__ITEMS__', JSON.stringify(plan))
  .replace('__DELAY__', String(delayMs)));
process.stdout.write(out);
