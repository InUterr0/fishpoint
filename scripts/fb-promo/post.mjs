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
// --slug=<slug>: wskaż konkretny wpis zamiast brać najświeższe. Przydatne, gdy
// powodem posta jest aktualizacja starszego materiału, a nie jego publikacja.
const slugArg = process.argv.find(a => a.startsWith('--slug='));
const wantSlug = slugArg?.split('=')[1] || null;
// --text=<treść>: własny tekst posta zamiast składanego z tytułu i opisu meta.
const textArg = process.argv.find(a => a.startsWith('--text='));
const customText = textArg ? textArg.slice('--text='.length) : null;

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
const selected = wantSlug
  ? pool.filter(x => x.slug === wantSlug).slice(0, 1)
  : all ? pool.slice(0, 6) : pool.slice(0, count);
if (wantSlug && selected.length === 0) {
  console.log('[fb] Nie znaleziono nieopublikowanego wpisu o slugu: ' + wantSlug);
  process.exit(1);
}

if (selected.length === 0) {
  console.log('[fb] Brak nowych, nieopublikowanych artykułów. Nic do wrzucenia.');
  process.exit(0);
}

// Tekst posta: zwięzły lead z tytułu + opis meta + link + hashtagi.
const plan = selected.map((a, i) => {
  // Tytuł strony niesie sufiks marki („… | FishPoint"), zbędny w poście na
  // profilu FishPoint — podpis i tak widnieje nad treścią.
  const lead = a.title.replace(/\s*[|—-]\s*FishPoint\s*$/u, '').trim();
  const text = customText || `${lead}\n\n${a.description}\n\n\u{1F449} ${a.url}\n\n#wędkarstwo #FishPoint`;
  return {
    n: i + 1,
    slug: a.slug,
    title: a.title,
    url: a.url,
    text,
    // Publikację potwierdzamy po fragmencie FAKTYCZNEJ treści posta, a nie po
    // tytule artykułu: przy własnym tekście (--text) tytuł w poście nie pada,
    // więc weryfikacja po nim dawała fałszywe „nieopublikowano".
    verify: text.split('\n')[0].slice(0, 60),
  };
});

if (dryRun) {
  console.log(JSON.stringify(plan, null, 2));
  process.exit(0);
}

if (!existsSync(SHOTS)) mkdirSync(SHOTS, { recursive: true });

// Współrzędne kompozytora strony (viewport CDP 1920x1200, bez chrome).
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
    # Szuka WIDOCZNEGO, aktywnego przycisku o danym tekście w dowolnym dialogu,
    # a następnie klika jego środek przez browser-harness. Natywny klik jest
    # konieczny, bo syntetyczne zdarzenia DOM bywają ignorowane przez Reacta FB.
    payload = js(r'''(() => {
      const want = __LABELS__;
      const all = Array.from(document.querySelectorAll('[role="button"], button'));
      for (const label of want) {
        let best = null;
        for (const e of all) {
          const txt = (e.innerText || e.textContent || '').trim();
          const aria = e.getAttribute('aria-label') || '';
          if (txt !== label && aria !== label) continue;
          if (e.getAttribute('aria-disabled') === 'true' || e.disabled) continue;
          const r = e.getBoundingClientRect();
          if (r.width < 60 || r.height < 20 || r.y < 0 || r.y > 1200) continue;
          if (!e.closest('div[role="dialog"]')) continue;
          if (!best || r.width > best.width) {
            best = { label, width: r.width, element: e };
          }
        }
        if (best) {
          best.element.scrollIntoView({ block: 'center', inline: 'nearest' });
          const r = best.element.getBoundingClientRect();
          return JSON.stringify({
            label: best.label,
            x: r.x + r.width / 2,
            y: Math.min(r.y + r.height / 2, 1195),
            width: r.width,
          });
        }
      }
      return '';
    })()'''.replace('__LABELS__', __import__('json').dumps(labels)))
    raw = (payload or '').strip().strip('"').replace('\\"', '"')
    if not raw:
        return ''
    target = __import__('json').loads(raw)
    click_at_xy(target['x'], target['y'])
    return target['label']


def scheduling_dialog_open():
    # Widoczne okno planowania oznacza, że klik minął przycisk publikacji.
    return js(r'''(() =>
      (document.body.innerText || '').includes('Zaplanuj na później') ? '1' : '0'
    )()''').strip().strip('"') == '1'

def settings_screen_open():
    # Drugi krok kompozytora ma własny nagłówek. Bez tego sprawdzenia skrypt
    # klikał „Dalej" jeszcze w trakcie animacji przejścia i gubił „Opublikuj".
    return js(r'''(() =>
      (document.body.innerText || '').includes('Ustawienia posta') ? '1' : '0'
    )()''').strip().strip('"') == '1'


def click_target(labels=None, textbox=False, in_dialog=False):
    payload = js(r'''(() => {
      const labels = __LABELS__;
      const textbox = __TEXTBOX__;
      const inDialog = __IN_DIALOG__;
      const all = Array.from(document.querySelectorAll(
        '[role="button"], button, [role="textbox"][contenteditable="true"]'
      ));
      let best = null;
      for (const e of all) {
        const txt = (e.innerText || e.textContent || '').trim();
        const aria = e.getAttribute('aria-label') || '';
        const matches = textbox
          ? e.getAttribute('role') === 'textbox'
          : labels.some(label => txt === label || aria === label);
        if (!matches) continue;
        if (inDialog && !e.closest('div[role="dialog"]')) continue;
        const r = e.getBoundingClientRect();
        if (r.width < 40 || r.height < 20 || r.y < 0 || r.y > 1200) continue;
        const area = r.width * r.height;
        if (!best || area > best.area) {
          best = { x: r.x + r.width / 2, y: r.y + r.height / 2, area };
        }
      }
      return best ? JSON.stringify({ x: best.x, y: best.y }) : '';
    })()'''
      .replace('__LABELS__', __import__('json').dumps(labels or []))
      .replace('__TEXTBOX__', 'true' if textbox else 'false')
      .replace('__IN_DIALOG__', 'true' if in_dialog else 'false'))
    raw = (payload or '').strip().strip('"').replace('\\"', '"')
    if not raw:
        return False
    point = __import__('json').loads(raw)
    click_at_xy(point['x'], point['y'])
    return True


def composer_open():
    # Czy w dialogu wciąż jest widoczny przycisk Dalej/Opublikuj (kompozytor żyje)?
    return js(r'''(() => {
      const all=Array.from(document.querySelectorAll('[role="button"]'));
      for(const e of all){const t=(e.innerText||e.textContent||'').trim();const a=e.getAttribute('aria-label')||'';
        if((/^(Dalej|Opublikuj)$/.test(t)||/^(Dalej|Opublikuj)$/.test(a))&&e.closest('div[role="dialog"]')){
          const r=e.getBoundingClientRect(); if(r.width>60&&r.y>=0&&r.y<=1200) return '1';}}
      return '0';
    })()''').strip().strip('"') == '1'


def post_visible(title):
    result = js(r'''(() => {
      const title = __TITLE__;
      const posts = document.querySelectorAll(
        '[role="article"], [data-pagelet*="FeedUnit"]'
      );
      for (const post of posts) {
        if (post.closest('div[role="dialog"]')) continue;
        const text = post.innerText || post.textContent || '';
        if (text.includes(title) && text.includes('Przed chwilą')) return '1';
      }
      return '0';
    })()'''.replace('__TITLE__', __import__('json').dumps(title)))
    return result.strip().strip('"') == '1'

def post_one(idx, item):
    # Świeża karta FB (uaktywnia ją) — wszystko dzieje się na niej.
    new_tab('https://www.facebook.com/')
    wait_for_load(); time.sleep(9)
    # Większy viewport utrzymuje przyciski pod wielowierszowym opisem i
    # podglądem linku w zasięgu natywnego kliknięcia.
    cdp('Emulation.setDeviceMetricsOverride',
        width=1920, height=1200, deviceScaleFactor=1, mobile=False)
    time.sleep(2)
    textbox_clicked = False
    composer_found = False
    for _ in range(3):
        if click_target(['O czym myślisz, FishPoint?']):
            composer_found = True
        for _ in range(6):
            time.sleep(2)
            if click_target(textbox=True, in_dialog=True):
                textbox_clicked = True
                break
        if textbox_clicked:
            break
        time.sleep(2)
    if not composer_found:
        raise RuntimeError('brak kompozytora strony FishPoint')
    if not textbox_clicked:
        raise RuntimeError('brak pola tekstowego kompozytora')
    time.sleep(1)
    type_text(item['text'])
    # FB nie przechodzi dalej, dopóki asynchronicznie buduje podgląd linku.
    # Sam przycisk potrafi już wyglądać na aktywny, więc czekamy na zniknięcie
    # komunikatu zamiast klikać go w trakcie generowania.
    time.sleep(8)
    for _ in range(30):
        building_preview = js(r'''(() =>
          (document.body.innerText || '').includes('Tworzenie podglądu linku') ? '1' : '0'
        )()''').strip().strip('"') == '1'
        if not building_preview:
            break
        time.sleep(2)
    shot('wpisano-%d' % idx)
    # Klikaj „Dalej" aż pojawi się „Opublikuj". Facebook może następnie
    # otworzyć dodatkowy krok „Udostępnij w grupach”; pierwszy klik jeszcze
    # wtedy nie publikuje posta na stronie, więc zatwierdzamy ten krok raz.
    published = False
    for step in range(12):
        clicked = click_button(['Opublikuj', 'Dalej'])
        if clicked == 'Opublikuj':
            print('[fb] %d klik: Opublikuj' % idx)
            time.sleep(9)
            # Jeśli klik minął CTA i otworzył planowanie, wycofaj się i spróbuj
            # jeszcze raz zamiast zostawiać post zaplanowany albo porzucony.
            if scheduling_dialog_open():
                print('[fb] %d planowanie zamiast publikacji — wycofuję' % idx)
                click_button(['Wstecz'])
                time.sleep(4)
                continue
            published = not composer_open() or post_visible(item['verify'])
            break
        elif clicked == 'Dalej':
            print('[fb] %d klik: Dalej' % idx)
            # Przejście na „Ustawienia posta" potrafi trwać kilkanaście sekund.
            # Czekamy na nie aktywnie: sztywna pauza kończyła się ponownym
            # kliknięciem znikającego „Dalej" i pętla nigdy nie widziała CTA.
            for _ in range(15):
                time.sleep(2)
                if settings_screen_open():
                    print('[fb] %d ekran: Ustawienia posta' % idx)
                    break
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
