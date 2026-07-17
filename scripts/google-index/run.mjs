#!/usr/bin/env node
// Automates Google Search Console "Request indexing" for the freshest articles.
//
// Google has no public API for manual indexing of ordinary article pages
// (the Indexing API is officially JobPosting/BroadcastEvent only), so this
// drives the logged-in GSC "Inspect URL" → "Request indexing" flow in a real
// browser via browser-harness — exactly the manual clicks, automated.
//
// Usage:
//   node scripts/google-index/run.mjs [--dry-run] [--count=15]
//        [--property=sc-domain:fish-point.pl] [--delay-ms=8000]
//
// Notes:
//   - GSC limits manual requests to ~10-12/day per property; excess URLs hit a
//     daily-quota wall and are reported as skipped (not an error).
//   - Requires a browser-harness session already logged into the Google
//     account that owns the GSC property.
import { spawnSync } from 'node:child_process';
import { latestArticles } from '../lib/latest-articles.mjs';

const arg = (name, def) => {
  const a = process.argv.find(x => x.startsWith(`--${name}=`));
  return a ? a.split('=').slice(1).join('=') : def;
};

const count = Math.min(Number(arg('count', 15)), 30);
const property = arg('property', 'sc-domain:fish-point.pl');
const userIdx = arg('user', '0'); // Google multi-account index (/u/<n>/)
const delayMs = Number(arg('delay-ms', 8000));
const dryRun = process.argv.includes('--dry-run');

const urls = latestArticles(process.cwd(), count).map(a => a.url);

// GSC's deep inspect?id= link 404s; the working entry is the console home for
// the property, then each URL is typed into the top "Inspect any URL" box.
const consoleUrl =
  `https://search.google.com/u/${userIdx}/search-console?resource_id=${encodeURIComponent(property)}`;

if (dryRun) {
  console.log(JSON.stringify({ property, consoleUrl, count: urls.length, urls }, null, 2));
  process.exit(0);
}

function runHarness(code) {
  const r = spawnSync('bash', ['-lc', 'browser-harness'], { input: code, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
  process.stdout.write(r.stdout || '');
  if (r.status !== 0) throw new Error(r.stderr || r.stdout || 'harness failed');
}

const py = String.raw`
import time, json, os
from urllib.parse import urlparse, parse_qs

urls = __URLS__
console_url = __CONSOLE__
delay_ms = __DELAY_MS__
property = __PROPERTY__
evidence_dir = 'obrazy/google-index'
os.makedirs(evidence_dir, exist_ok=True)


def shot(label=''):
    try:
        safe = ''.join(c if c.isalnum() or c in '-_' else '-' for c in str(label))[:80] or 'shot'
        path = f'{evidence_dir}/{int(time.time())}-{safe}.png'
        capture_screenshot(path)
        print(f'[gindex] screenshot {label}: {path}')
        return path
    except Exception as e:
        print(f'[gindex] screenshot failed: {e}')
        return None


def body_text():
    try:
        return js('document.body.innerText') or ''
    except Exception:
        return ''


def fishpoint_console_tabs():
    matches = []
    for tab in list_tabs(include_chrome=False):
        try:
            parsed = urlparse(tab.get('url') or '')
            resource = parse_qs(parsed.query).get('resource_id', [''])[0]
            if parsed.netloc == 'search.google.com' and '/search-console' in parsed.path and resource == property:
                matches.append(tab)
        except Exception:
            continue
    return matches


def console_authenticated():
    try:
        parsed = urlparse((current_tab().get('url') or '').lower())
        if parsed.netloc in ('accounts.google.com', 'consent.google.com'):
            return False
    except Exception:
        return False
    txt = body_text().lower()
    login_markers = ('sign in to search console', 'zaloguj się w search console', 'choose an account', 'wybierz konto')
    return not any(marker in txt for marker in login_markers)


def activate_console_tab():
    """Reuse exactly one FishPoint GSC tab; create one replacement only if it was closed."""
    tabs = fishpoint_console_tabs()
    if tabs:
        keep = tabs[0]
        for duplicate in tabs[1:]:
            try:
                close_tab(duplicate)
                print(f"[gindex] closed duplicate FishPoint console tab: {duplicate['targetId']}")
            except Exception as e:
                print(f'[gindex] duplicate tab close failed: {str(e)[:80]}')
        switch_tab(keep)
    else:
        print(f'[gindex] opening console: {console_url}')
        new_tab(console_url)
        try:
            wait_for_load()
        except Exception as e:
            print(f'[gindex] console nav slow ({e}); continuing')
        time.sleep(8)
    if not console_authenticated():
        shot('auth-blocked')
        print('[gindex] AUTH_BLOCKED: logged-in Search Console access is required')
        return False
    return True

def js_retry(code, tries=6, wait=4):
    for k in range(tries):
        try:
            return js(code)
        except Exception as e:
            print(f'[gindex] page busy ({str(e)[:80]}); retry {k+1}/{tries}')
            time.sleep(wait)
    return None


# Localised button/label matchers (EN + PL Search Console UI).
REQUEST_RE = r'(request indexing|popro[sś] o zindeksowanie|popro[sś] o indeksowanie)'
QUOTA_RE = r'(exceeded your daily quota|reached your daily quota|przekroczono dzienny limit|wyczerpano dzienny limit|limit dzienny|przekroczono limit|spr[oó]buj ponownie jutro|try again tomorrow|został przekroczony)'
DONE_RE = r'(indexing requested|requested indexing|za[zż][aą]dano indeksowania|poproszono o zindeksowan|przes[lł]ano pro[sś]b[eę]|url added to|added to a priority crawl queue|do kolejki priorytetow|dodano do kolejki|dodany do kolejki)'
ALREADY_RE = r'(url is on google|adres url jest w google)'


def click_request_indexing():
    # Find the "Request indexing / Poproś o zindeksowanie" control and click it.
    # Match clickable elements whose text mentions (re)indexing — but NOT the
    # left-nav "Indeksowanie" section header. Returns clicked text, '__dbg__' +
    # candidate dump when nothing matched, or None on JS failure.
    code = (r'''(()=>{
      const want=/(request indexing|popro\S* o (z)?indeksowan|za(z|ż)(a|ą)daj indeksowan)/i;
      const sel='a,button,[role="button"],[role="link"]';
      const nodes=[...document.querySelectorAll(sel)];
      const cands=[];
      for(const n of nodes){
        const r=n.getBoundingClientRect();
        if(r.width<4||r.height<4) continue;
        const t=(n.innerText||n.textContent||'').replace(/\s+/g,' ').trim();
        if(!t||t.length>70) continue;
        if(/indeksowan|indexing/i.test(t)) cands.push(t);
        if(want.test(t)){
          n.scrollIntoView({block:'center'});
          n.click();
          return 'CLICK::'+t;
        }
      }
      return 'MISS::'+JSON.stringify(cands.slice(0,12));
    })()''')
    res = js_retry(code, tries=3, wait=3)
    if not res:
        return None
    if res.startswith('CLICK::'):
        return res[7:]
    print(f'[gindex] no match; index-related clickables seen: {res[6:]}')
    return None


def inspect_state():
    # Classify the current page after an inspection / request attempt.
    txt = body_text().lower()
    import re
    if re.search(QUOTA_RE, txt): return 'quota'
    if re.search(DONE_RE, txt): return 'done'
    if re.search(ALREADY_RE, txt): return 'already'
    return 'unknown'


def find_inspect_box():
    # Locate the top "Inspect any URL in ..." search box; return its center xy.
    code = (r'''(()=>{
      const re=/(sprawd[zź].*url|inspect.*url)/i;
      const cands=[...document.querySelectorAll('input,[role="textbox"],[contenteditable="true"],textarea')];
      for(const n of cands){
        const r=n.getBoundingClientRect();
        if(r.width<40||r.height<8) continue;
        const t=((n.getAttribute('aria-label')||'')+' '+(n.getAttribute('placeholder')||'')).trim();
        if(re.test(t)) return [r.left+r.width/2, r.top+r.height/2, t];
      }
      // Fallback: the widest visible text input near the top of the page.
      let best=null;
      for(const n of cands){
        const r=n.getBoundingClientRect();
        if(r.top>140||r.width<200||r.height<8) continue;
        if(!best||r.width>best[3]) best=[r.left+r.width/2, r.top+r.height/2, '', r.width];
      }
      return best?[best[0],best[1],best[2]]:null;
    })()''')
    return js_retry(code, tries=6, wait=3)


def focus_inspect_box():
    # Focus + clear the inspect search input via JS (more reliable than a blind
    # click on the SPA box). Returns the matched placeholder/label, or None.
    code = (r'''(()=>{
      const re=/(sprawd[zź].*url|inspect.*url)/i;
      const cands=[...document.querySelectorAll('input,[role="textbox"],textarea')];
      let el=cands.find(n=>{const t=((n.getAttribute('aria-label')||'')+' '+(n.getAttribute('placeholder')||''));return re.test(t)&&n.getBoundingClientRect().width>40;});
      if(!el){ el=cands.filter(n=>{const r=n.getBoundingClientRect();return r.top<160&&r.width>200;}).sort((a,b)=>b.getBoundingClientRect().width-a.getBoundingClientRect().width)[0]; }
      if(!el) return null;
      el.scrollIntoView({block:'center'}); el.focus();
      try{ el.select&&el.select(); }catch(e){}
      const lbl=(el.getAttribute('aria-label')||el.getAttribute('placeholder')||'').trim();
      const r=el.getBoundingClientRect();
      return {lbl, x:r.left+r.width/2, y:r.top+r.height/2};
    })()''')
    return js_retry(code, tries=6, wait=3)


def inspect_url_via_box(url, idx):
    info = focus_inspect_box()
    if not info:
        return False
    # Click to make sure the SPA registers focus, then type + submit.
    click_at_xy(float(info['x']), float(info['y']))
    time.sleep(1)
    type_text(url)
    time.sleep(1)
    press_key('Enter')
    time.sleep(2)
    # Fallback: some GSC builds don't submit on a bare keypress — dispatch a
    # full Enter sequence on the focused input.
    js_retry(r'''(()=>{const el=document.activeElement; if(!el) return false;
      for(const type of ['keydown','keypress','keyup']){
        el.dispatchEvent(new KeyboardEvent(type,{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));
      }
      // Also try submitting an enclosing form, if any.
      const f=el.closest('form'); if(f&&f.requestSubmit){try{f.requestSubmit();}catch(e){}}
      return true;})()''', tries=2, wait=1)
    return True


def process_one(url, idx, total):
    print(f'[gindex] {idx}/{total} inspecting: {url}')
    if not inspect_url_via_box(url, idx):
        shot(f'no-box-{idx}')
        print(f'[gindex] {idx}: inspect search box not found')
        return 'no-box'
    # GSC runs the inspection after submit — give it time to finish.
    time.sleep(12)
    # Wait until the inspection result (and the Request-indexing link) renders.
    # The inspection itself can take ~30-60s before the button appears.
    clicked = None
    for _ in range(18):
        clicked = click_request_indexing()
        if clicked:
            break
        time.sleep(4)
    if not clicked:
        st = inspect_state()
        if st == 'quota':
            shot(f'quota-{idx}')
            return 'quota'
        shot(f'no-button-{idx}')
        print(f'[gindex] {idx}: request-indexing control not found (state={st})')
        return 'no-button'
    print(f'[gindex] {idx}: clicked request indexing; waiting for live test')
    # The request runs a live URL test (can take 30-90s) before confirming.
    result = 'unknown'
    for _ in range(30):
        time.sleep(5)
        st = inspect_state()
        if st in ('done', 'quota', 'already'):
            result = st
            break
    shot(f'{result}-{idx}')
    print(f'[gindex] {idx}: result={result}')
    # Dismiss any open dialog so the next tab starts clean.
    js_retry(r'''(()=>{const re=/(^|\s)(got it|ok|close|zamknij|rozumiem)(\s|$)/i;
      for(const b of document.querySelectorAll('button,[role="button"]')){
        const t=(b.innerText||'').trim(); if(t&&t.length<24&&re.test(t)){b.click();return t;}}
      return null;})()''', tries=2, wait=2)
    return result


counts = {'done':0,'quota':0,'already':0,'no-button':0,'no-box':0,'unknown':0,'auth-blocked':0}
quota_hit = False
auth_blocked = False
total = len(urls)

# Reuse the authorization tab opened before the audit. If it was closed,
# activate_console_tab creates one replacement and applies the same auth gate.
if not activate_console_tab():
    auth_blocked = True

for i,u in enumerate(urls, start=1):
    if auth_blocked:
        print(f'[gindex] {i}/{total} skipped (authorization blocked): {u}')
        counts['auth-blocked'] += 1
        continue
    if quota_hit:
        print(f'[gindex] {i}/{total} skipped (daily quota already hit): {u}')
        counts['quota']+=1
        continue
    try:
        if not activate_console_tab():
            auth_blocked = True
            counts['auth-blocked'] += 1
            print('[gindex] authorization lost — remaining URLs will be skipped')
            continue
        r = process_one(u, i, total)
    except Exception as e:
        print(f'[gindex] {i}: error {str(e)[:120]}')
        r = 'unknown'
    counts[r]=counts.get(r,0)+1
    if r == 'quota':
        quota_hit = True
        print('[gindex] daily quota reached — remaining URLs will be skipped')
    time.sleep(delay_ms/1000.0)

print(f'[gindex] DONE property={property} total={total} ' +
      ' '.join(f'{k}={v}' for k,v in counts.items()))
`;

const code = py
  .replace('__URLS__', JSON.stringify(urls))
  .replace('__CONSOLE__', JSON.stringify(consoleUrl))
  .replace('__DELAY_MS__', String(delayMs))
  .replace('__PROPERTY__', JSON.stringify(property));

runHarness(code);
