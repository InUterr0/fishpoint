#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { latestArticles } from '../lib/latest-articles.mjs';

// Targets are drawn at RANDOM from the published articles — not "the newest".
// Read a wide pool of articles, then shuffle so each run promotes a different,
// arbitrary mix. Use --latest=N to widen/narrow the candidate pool.
const latestArg = process.argv.find(a => a.startsWith('--latest='));
const poolSize = Number(latestArg?.split('=')[1] || 50);
// Wspólny leksykon wędkarski: post w wynikach FB musi zahaczać o TEMAT, inaczej
// nie komentujemy (żeby artykuł wędkarski nie trafił pod post o sukienkach itp.).
const FISHING_LEXICON = [
  'wędk', 'ryb', 'połów', 'połow', 'łowi', 'lowi', 'spinning', 'spinningow',
  'feeder', 'method', 'grunt', 'spławik', 'splawik', 'muchow', 'muszk',
  'szczupak', 'okoń', 'okon', 'sandacz', 'karp', 'leszcz', 'płoć', 'ploc',
  'lin ', 'sum', 'pstrąg', 'pstrag', 'kleń', 'klen', 'jaź', 'jaz', 'boleń', 'bolen',
  'przynęt', 'przynet', 'wobler', 'błystk', 'blystk', 'guma', 'twister', 'jig',
  'kołowrotek', 'kolowrotek', 'żyłka', 'zylka', 'plecionka', 'haczyk', 'kotwic',
  'spławik', 'zanęt', 'zanet', 'przyponów', 'przypon', 'wędzisk', 'wedzisk',
  'jezioro', 'rzeka', 'staw', 'łowisko', 'lowisko', 'zbiornik', 'brania', 'branie',
  'zacięcie', 'zaciecie', 'hol ', 'holowan', 'zasiadk', 'wyprawa', 'zawody',
];
// Zbiera słowa-klucze tematyczne dla artykułu: leksykon + mocne słowa z tytułu,
// zapytania i slug-a (po polsku, małymi literami, bez ogonkowych wariantów).
function topicKeywords(a) {
  const fromText = `${a.title} ${a.query} ${a.slug.replace(/-/g, ' ')}`
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .split(/\s+/)
    .filter(w => w.length >= 4)
    .map(w => w.slice(0, 6)); // przedrostek, by łapać odmiany
  return [...new Set([...FISHING_LEXICON, ...fromText])];
}
const pool = latestArticles(process.cwd(), poolSize).map(a => ({
  slug: a.slug,
  url: a.url,
  search: `https://www.facebook.com/search/posts?q=${encodeURIComponent(a.query)}`,
  comment: `${a.note} Więcej: ${a.url}`,
  topic: topicKeywords(a),
}));
// Fisher–Yates shuffle: pick articles in a random order every run.
for (let i = pool.length - 1; i > 0; i--) {
  const j = Math.floor(Math.random() * (i + 1));
  [pool[i], pool[j]] = [pool[j], pool[i]];
}

// Per-article rotation: each run targets articles we haven't used as comment
// subjects yet, so we don't keep hammering the same stale top-of-pool topics.
// Once every pooled article has been used, the cycle resets. Pass --no-rotate
// to ignore the history and always take the freshest articles.
const USED_PATH = 'scripts/facebook-comments/.used-articles.json';
const rotate = !process.argv.includes('--no-rotate');
function loadUsed() {
  try { return new Set(JSON.parse(readFileSync(USED_PATH, 'utf8'))); }
  catch { return new Set(); }
}
function saveUsed(set) {
  try { writeFileSync(USED_PATH, JSON.stringify([...set], null, 0)); }
  catch (e) { console.log(`[fejs-komcie] used-articles save failed: ${e.message}`); }
}
let used = rotate ? loadUsed() : new Set();
let fresh = pool.filter(t => !used.has(t.slug));
if (rotate && fresh.length === 0) {
  // Whole pool exhausted — reset the cycle and start over from the top.
  console.log('[fejs-komcie] rotation: all pooled articles used; resetting cycle');
  used = new Set();
  fresh = pool.slice();
}
const targets = fresh;

const dryRun = process.argv.includes('--dry-run');
const countArg = process.argv.find(a => a.startsWith('--count='));
const delayArg = process.argv.find(a => a.startsWith('--delay-ms='));
const count = Math.min(Number(countArg?.split('=')[1] || 2), 4);
const delayMs = Number(delayArg?.split('=')[1] || 90000);
const minSuccessArg = process.argv.find(a => a.startsWith('--min-success='));
const maxAttemptsArg = process.argv.find(a => a.startsWith('--max-attempts='));
const minCommentsArg = process.argv.find(a => a.startsWith('--min-comments='));
const minComments = Number(minCommentsArg?.split('=')[1] || 20);
// Placement quality knobs: only comment under posts that are still *alive*
// (recent) and reach a real audience (big page / high reaction floor).
const maxAgeHoursArg = process.argv.find(a => a.startsWith('--max-age-hours='));
const maxAgeHours = Number(maxAgeHoursArg?.split('=')[1] || 48);
const minReactionsArg = process.argv.find(a => a.startsWith('--min-reactions='));
const minReactions = Number(minReactionsArg?.split('=')[1] || 50);
// Defaults are skip-friendly: an item with no suitable target post is dropped,
// not retried, and a partial run is reported as success (exit 0). Pass
// --min-success=N / --max-attempts=N to enforce stricter guarantees.
const minSuccess = Math.min(Number(minSuccessArg?.split('=')[1] || 0), count);
const maxAttempts = Math.max(Number(maxAttemptsArg?.split('=')[1] || 1), 1);
const selected = targets.slice(0, count);

if (dryRun) {
  console.log(JSON.stringify(selected.map(({ slug, ...rest }) => rest), null, 2));
  process.exit(0);
}

// Mark the chosen articles as used so the next run rotates to different ones.
if (rotate) {
  selected.forEach(t => used.add(t.slug));
  saveUsed(used);
  console.log(`[fejs-komcie] rotation: marked ${selected.length} article(s) used (${used.size}/${pool.length} of pool)`);
}

function runHarness(code) {
  const r = spawnSync('bash', ['-lc', 'browser-harness'], { input: code, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
  if (r.status !== 0) throw new Error(r.stderr || r.stdout);
  process.stdout.write(r.stdout);
}

const py = String.raw`
import time, json
items = __ITEMS__
delay_ms = __DELAY_MS__
min_success = __MIN_SUCCESS__
max_attempts = __MAX_ATTEMPTS__
min_comments = __MIN_COMMENTS__
max_age_hours = __MAX_AGE_HOURS__
min_reactions = __MIN_REACTIONS__
import os
evidence_dir = 'obrazy/fejs-komcie'
# Persistent dedup: posts we've already commented under (across runs). Keyed by
# a stable post id (pfbid/story_fbid/permalink) and/or a content signature.
SEEN_PATH = 'scripts/facebook-comments/.commented-posts.json'
PAGE_NAME = 'FishPoint'


def load_seen():
    try:
        with open(SEEN_PATH, encoding='utf-8') as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(s):
    try:
        with open(SEEN_PATH, 'w', encoding='utf-8') as f:
            json.dump(sorted(s), f, ensure_ascii=False, indent=0)
    except Exception as e:
        print(f'[fejs-komcie] seen save failed: {e}')


seen = load_seen()
print(f'[fejs-komcie] dedup: {len(seen)} known posts loaded from {SEEN_PATH}')
PAGE_ID = '61591546555168'
# Personal accounts that must NEVER author these comments. If any of these is the
# acting FB identity, the whole run is aborted before anything is published.
BAD_ACCOUNTS = ['Maciek Baniewicz', 'faschowiecpro', 'Faschowiec', 'Fachowiec.pro', 'World News No Spin']


def body_text():
    try:
        return js('document.body.innerText') or ''
    except Exception:
        return ''


def shot(label=''):
    try:
        import os, time as _time
        os.makedirs(evidence_dir, exist_ok=True)
        safe = ''.join(c if c.isalnum() or c in '-_' else '-' for c in str(label))[:80] or 'shot'
        path = f'{evidence_dir}/{int(_time.time())}-{safe}.png'
        capture_screenshot(path)
        print(f'[fejs-komcie] screenshot {label}: {path}')
        return path
    except Exception as e:
        print(f'[fejs-komcie] screenshot failed: {e}')
        return None


class WrongIdentity(Exception):
    # Raised to abort the ENTIRE run — never caught per-item.
    pass


def identity_probe():
    # Read the acting FB identity from avatar/account aria-labels and alt text.
    # Returns {pageSeen, badSeen, badHit, labels}. We scan visible labelled
    # elements because FB tags the acting profile's avatar with its name.
    cfg = json.dumps({'page': PAGE_NAME, 'bad': BAD_ACCOUNTS})
    res = js(r'''((cfg)=>{
      const {page, bad} = cfg;
      const esc=s=>s.replace(/[.*+?^\${}()|[\]\\]/g,'\\$&');
      const labels=[];
      document.querySelectorAll('[aria-label],[alt],a[href*="profile.php"],a[href]').forEach(e=>{
        const r=e.getBoundingClientRect();
        if(r.width<8||r.height<8) return;
        const t=((e.getAttribute('aria-label')||'')+' '+(e.getAttribute('alt')||'')+' '+(e.getAttribute('href')||'')).trim();
        if(t) labels.push(t);
      });
      const text=labels.join(' | ');
      const pageSeen=new RegExp(esc(page),'i').test(text);
      let badHit=null;
      for(const b of bad){ if(new RegExp(esc(b),'i').test(text)){ badHit=b; break; } }
      return {pageSeen, badSeen: !!badHit, badHit, sample: labels.slice(0,30)};
    })(''' + cfg + r''')''')
    return res or {'pageSeen': False, 'badSeen': False, 'badHit': None, 'sample': []}


def assert_page_identity(context='preflight'):
    # HARD GATE. Confirm we are acting as the Page and NOT a personal
    # account. Fail-safe: if a bad account is detected, OR the page identity
    # cannot be positively confirmed, abort the whole run — do not publish.
    p = js_retry(identity_probe, tries=4, wait=3) or {}
    badHit = p.get('badHit')
    pageSeen = p.get('pageSeen')
    print(f'[fejs-komcie] identity[{context}]: pageSeen={pageSeen} badHit={badHit}')
    if badHit:
        shot(f'wrong-identity-{context}')
        raise WrongIdentity(f'WRONG IDENTITY: acting account looks like "{badHit}", expected page "{PAGE_NAME}". Sample labels: {p.get("sample")}')
    if not pageSeen:
        shot(f'identity-unconfirmed-{context}')
        raise WrongIdentity(f'identity gate failed: could not confirm acting identity is "{PAGE_NAME}" ({context}). Refusing to publish. Sample labels: {p.get("sample")}')
    return True


def click_text(patterns):
    # Click the FIRST visible element whose text/aria-label matches any of the
    # given (case-insensitive) regex patterns. Returns the matched label or None.
    cfg = json.dumps({'pats': patterns})
    return js(r'''((cfg)=>{
      const {pats}=cfg;
      const els=[...document.querySelectorAll('[role="button"],[role="menuitem"],[role="link"],a,span,div[tabindex]')];
      for(const p of pats){
        const rx=new RegExp(p,'i');
        for(const e of els){
          const r=e.getBoundingClientRect();
          if(r.width<8||r.height<8) continue;
          const t=((e.innerText||'')+' '+(e.getAttribute('aria-label')||'')).trim();
          if(t && rx.test(t)){ e.scrollIntoView({block:'center'}); e.click(); return t.slice(0,80); }
        }
      }
      return null;
    })(''' + cfg + r''')''')


def switch_to_page():
    # Try to switch the acting FB identity to the FishPoint Page via the account
    # switcher menu. Best-effort: open the account menu, hit "Switch profile",
    # then click the entry whose name matches PAGE_NAME. Re-probe to confirm.
    print(f'[fejs-komcie] wrong identity — trying to switch to "{PAGE_NAME}"')
    esc = PAGE_NAME.replace('.', r'\.')
    for attempt in range(3):
        # Navigate in the SAME tab — never spawn new tabs on each attempt.
        goto_url('https://www.facebook.com/')
        try:
            wait_for_load()
        except Exception:
            pass
        time.sleep(4)
        # Open the account menu (top-right). FB renders a "Szybkie przełączanie
        # profili" panel with a direct "Przełącz na profil <Name>" control.
        opened = click_text(['^Twoje konto', '^Konto$', '^Account$', 'Twój profil', 'Menu konta', 'Your profile'])
        print(f'[fejs-komcie] account menu[{attempt}]: {opened}')
        time.sleep(3)
        # Click the explicit "switch to <PAGE_NAME>" control — match the precise
        # phrasing first so we never land on a different profile by accident.
        hit = click_text([
            f'Przełącz na profil {esc}',
            f'Switch to.*{esc}.*profile',
            f'Przejdź na profil {esc}',
        ])
        # If the Page is not in the quick-switch panel, open the full profile
        # list via "Zobacz wszystkie profile" and pick FishPoint there. FB then
        # shows a "Przełącz profil" confirm dialog with a blue "Przełącz" button.
        if not hit:
            seeall = click_text(['^Zobacz wszystkie profile$', '^See all profiles$'])
            print(f'[fejs-komcie] see-all-profiles[{attempt}]: {seeall}')
            time.sleep(5)
            hit = click_text([
                f'Przełącz na profil {esc}',
                f'Switch to.*{esc}.*profile',
                f'Przejdź na profil {esc}',
                f'^{esc}$',
            ])
        print(f'[fejs-komcie] switch click[{attempt}]: {hit}')
        time.sleep(4)
        # Confirm the "Przełącz profil" dialog if it appears (blue "Przełącz").
        confirm = js(r'''(()=>{
          const dlg=document.querySelector('[role="dialog"]')||document;
          const btns=[...dlg.querySelectorAll('[role="button"],button,a')];
          for(const b of btns){
            const r=b.getBoundingClientRect(); if(r.width<8||r.height<8) continue;
            const t=(b.innerText||'').trim();
            if(/^Przełącz$/i.test(t)){ b.scrollIntoView({block:'center'}); b.click(); return 'ok'; }
          }
          return null;
        })()''')
        if confirm:
            print(f'[fejs-komcie] confirm dialog[{attempt}]: {confirm}')
        time.sleep(5)
        try:
            wait_for_load()
        except Exception:
            pass
        time.sleep(4)
        p = js_retry(identity_probe, tries=3, wait=3) or {}
        if p.get('pageSeen') and not p.get('badHit'):
            print('[fejs-komcie] switch OK — now acting as the Page')
            return True
        shot(f'switch-attempt-{attempt}')
    print('[fejs-komcie] automatic switch failed')
    return False


def preflight_identity():
    # Open FB home once and ensure the session is acting as the Page before any
    # commenting begins. If we're on the wrong account, try to switch
    # automatically; only abort if the switch fails.
    new_tab('https://www.facebook.com/')
    try:
        wait_for_load()
    except Exception as e:
        print(f'[fejs-komcie] home nav slow ({e}); checking anyway')
    time.sleep(5)
    p = js_retry(identity_probe, tries=4, wait=3) or {}
    if not (p.get('pageSeen') and not p.get('badHit')):
        if not switch_to_page():
            assert_page_identity('home')  # raises WrongIdentity / aborts
    assert_page_identity('home')
    print('[fejs-komcie] preflight identity OK — acting as the FishPoint Page')


def js_retry(fn, tries=5, wait=4):
    # FB blocks its main thread right after load (autoplay, hydration) and CDP
    # evaluate calls time out — retry until the page becomes responsive.
    for k in range(tries):
        try:
            return fn()
        except Exception as e:
            print(f'[fejs-komcie] page busy ({str(e)[:80]}); retry {k+1}/{tries}')
            time.sleep(wait)
    return None


# Shared browser-side helpers for scoring/parsing a search-result card. Reused
# by both the picker and the diagnostic dump so they always agree.
CARD_JS = r'''
      const {minComments, maxAgeHours, minReactions, seen} = cfg;
      const seenSet = new Set(seen);
      function postId(card){
        for(const a of card.querySelectorAll('a[href]')){
          const h=a.getAttribute('href')||'';
          let m=h.match(/pfbid[0-9A-Za-z]+/); if(m) return 'fb:'+m[0];
          m=h.match(/story_fbid=([0-9A-Za-z.]+)/); if(m) return 'fb:sf:'+m[1];
          m=h.match(/\/posts\/([0-9A-Za-z.\-]+)/); if(m) return 'fb:p:'+m[1];
          m=h.match(/\/permalink\/(\d+)/); if(m) return 'fb:pl:'+m[1];
          m=h.match(/\/videos\/(\d+)/); if(m) return 'fb:v:'+m[1];
          m=h.match(/\/share\/[pv]\/([0-9A-Za-z]+)/); if(m) return 'fb:s:'+m[1];
        }
        return null;
      }
      function sig(card){
        return 'sig:'+(card.innerText||'').replace(/\s+/g,' ').trim().slice(0,120);
      }
      // Convert a numeric token ("6,9 tys.", "334", "1.2M") to a number. Tolerant
      // of surrounding text — grabs the FIRST number-with-optional-suffix it sees.
      function toNum(s){
        s=(s||'').replace(/ /g,' ');
        const m=s.match(/(\d[\d.,\s]*)\s*(tys\.?|mln|tho?u?sand|million|[KkMm])?/);
        if(!m) return null;
        let raw=m[1].replace(/\s/g,'');
        // "6,965" (en thousands) vs "6,9" (pl decimal): a comma followed by
        // exactly 3 digits at the end is a thousands separator.
        if(/,\d{3}$/.test(raw) || /\.\d{3}$/.test(raw)) raw=raw.replace(/[.,]/g,'');
        else raw=raw.replace(',', '.');
        let n=parseFloat(raw);
        if(isNaN(n)) return null;
        const suf=(m[2]||'').toLowerCase();
        if(/tys|thou|^k$/.test(suf)) n*=1000;
        else if(/mln|mill|^m$/.test(suf)) n*=1000000;
        return Math.round(n);
      }
      // Read reactions / comments / shares from the engagement bar. FB labels the
      // counts in aria-labels ("334 comments", "6,9 tys. reactions", PL
      // "334 komentarze", "241 udostępnienia") AND/OR as bare numbers at the
      // card tail. We try aria first (reliable), then fall back to the tail.
      function engagement(card){
        let reactions=null, comments=null, shares=null;
        const probe=[...card.querySelectorAll('[aria-label]')];
        for(const el of probe){
          const a=el.getAttribute('aria-label')||'';
          let m;
          if(comments===null && (m=a.match(/([\d.,\s]+(?:tys\.?|mln|[KkMm])?)\s*(?:comments?|komentarz)/i))) comments=toNum(m[1]);
          if(shares===null && (m=a.match(/([\d.,\s]+(?:tys\.?|mln|[KkMm])?)\s*(?:shares?|udost)/i))) shares=toNum(m[1]);
          if(reactions===null && (m=a.match(/([\d.,\s]+(?:tys\.?|mln|[KkMm])?)\s*(?:reactions?|polub|reakcj|like|likes)/i))) reactions=toNum(m[1]);
        }
        // Tail fallback: last bare numbers in the card text.
        const lines=(card.innerText||'').split('\n').map(x=>x.trim()).filter(Boolean);
        const tail=lines.slice(-8).map(x=>/^[\d.,\s]+(tys\.?|mln|[KkMm])?$/.test(x)?toNum(x):null).filter(v=>v!==null);
        if(reactions===null) reactions = tail.length>=3 ? tail[tail.length-3] : (tail[0]??0);
        if(comments===null)  comments  = tail.length>=2 ? tail[tail.length-2] : (tail[1]??0);
        if(shares===null)    shares    = tail.length>=1 ? tail[tail.length-1] : 0;
        return {reactions: reactions||0, comments: comments||0, shares: shares||0};
      }
      // The element to click to open the comment composer. Prefer an explicit
      // Comment/Skomentuj action button; fall back to the comment-count span.
      function commentTarget(card, comments){
        const btn=[...card.querySelectorAll('[role="button"],[aria-label],a')].find(e=>{
          const a=(e.getAttribute('aria-label')||'').toLowerCase();
          const t=(e.innerText||'').trim().toLowerCase();
          const hit=/skomentuj|komentarz|comment/.test(a) || /^skomentuj$|^comment$|^komentarze?$/.test(t);
          return hit && e.getBoundingClientRect().width>0;
        });
        if(btn) return btn;
        const span=[...card.querySelectorAll('span,div,a')].find(e=>{
          const v=toNum((e.innerText||'').trim());
          return v===comments && comments>0 && e.getBoundingClientRect().width>0 && (e.innerText||'').trim().length<=8;
        });
        return span||null;
      }
      function ageHours(card){
        const head=(card.innerText||'').split('\n').slice(0,8).join(' ');
        if(/teraz|just now|moments ago/i.test(head)) return 0;
        if(/wczoraj|yesterday/i.test(head)) return 24;
        const m=head.match(/(\d+)\s*(min|m(?![a-z])|godz|godziny?|g(?![a-z])|h(?![a-z])|hrs?|dni|dzień|d(?![a-z])|tyg|tydz|w(?![a-z]))/i);
        if(!m) return null;
        const n=parseInt(m[1],10); const u=m[2].toLowerCase();
        if(/^m/.test(u)) return n/60;
        if(/^(g|h)/.test(u)) return n;
        if(/^(d|dn|dz)/.test(u)) return n*24;
        if(/^(t|w)/.test(u)) return n*24*7;
        return null;
      }
      function scoreCard(card){
        const r=card.getBoundingClientRect();
        const {reactions, comments, shares}=engagement(card);
        const ours=/fish-point\.pl|FishPoint/i.test(card.innerText||'');
        const age=ageHours(card);
        const verified=!!card.querySelector('svg[aria-label*="erified"], svg[aria-label*="weryfik"], [aria-label*="Zweryfikowane"], [aria-label*="Verified account"]');
        const el=commentTarget(card, comments);
        const fresh = age===null ? 0.85 : Math.max(0.2, 1 + (maxAgeHours - age)/maxAgeHours);
        const reach = comments*4 + reactions + shares*6;
        const pid=postId(card); const psig=sig(card);
        return {reactions, comments, shares, ours, age, verified, el,
          pid, psig, seenBefore: seenSet.has(pid) || seenSet.has(psig),
          score: reach * fresh * (verified?1.35:1), visible: r.height>120};
      }
      function eligible(c){
        return c && c.visible && !c.ours && c.el && !c.seenBefore
          && c.comments>=minComments && (c.reactions>=minReactions || c.comments>=minComments*3)
          && (c.age===null || c.age<=maxAgeHours);
      }
'''


def open_nth_post(n):
    # Open the Nth post (0-based, top-to-bottom) from the search results by
    # clicking its comment-action button. Returns 'opened' / 'no-post' (n is
    # past the last visible result). Selection of WHICH post to keep is decided
    # later on the OPENED post body (see inspect_post) — here we only open it.
    cfg = json.dumps({'n': n})
    return js(r'''((cfg)=>{
      const {n}=cfg;
      function isComment(el){
        const a=(el.getAttribute('aria-label')||'').toLowerCase().trim();
        if(!a) return false;
        // The "write a comment" action: matches FB's "Dodaj komentarz" /
        // "Skomentuj" / "Napisz komentarz" (not "see N comments" previews).
        return /^skomentuj$|^komentarz$|napisz komentarz|dodaj komentarz|leave a comment|^comment$|write a comment/.test(a);
      }
      let cands=[...document.querySelectorAll('[role="button"],[aria-label]')]
        .filter(el=>{ if(!isComment(el)) return false;
          const r=el.getBoundingClientRect(); return r.width>0&&r.height>0&&r.top>140; });
      if(!cands.length){
        cands=[...document.querySelectorAll('[role="button"],[aria-label],a')]
          .filter(el=>{ const a=(el.getAttribute('aria-label')||'').toLowerCase();
            const r=el.getBoundingClientRect();
            return /komentarz|comment/.test(a) && r.width>0&&r.height>0&&r.top>140; });
      }
      cands.sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top);
      if(n>=cands.length) return 'no-post';
      cands[n].scrollIntoView({block:'center'}); cands[n].click(); return 'opened';
    })(''' + cfg + r''')''')


def inspect_post(topic):
    # Read the OPENED post dialog and judge relevance on the POST'S OWN BODY
    # only — everything BEFORE the comments section. This is the fix for the
    # "fishing article under a dresses post" bug: we must not match keywords that
    # belong to OTHER search results or to existing comments. Returns a JSON dict
    # {url, body, hits, bodyLen} or None when no dialog is open.
    cfg = json.dumps({'topic': topic or []})
    return js(r'''((cfg)=>{
      const topic=(cfg.topic||[]).map(s=>s.toLowerCase()).filter(Boolean);
      // Use the narrow post-viewer modal, not the full-page dialog (which also
      // contains nav + the whole results column).
      const dgs=[...document.querySelectorAll('[role="dialog"]')]
        .filter(d=>{const w=d.getBoundingClientRect().width; return w>350 && w<1000;});
      const dlg=dgs.pop()||[...document.querySelectorAll('[role="dialog"]')].pop();
      if(!dlg) return null;
      // Where do the comments start? (the sort bar "Najtrafniejsze/Najnowsze/…")
      let commentsTop=Infinity;
      for(const e of dlg.querySelectorAll('*')){
        const t=(e.innerText||'').trim();
        if(/^(Najtrafniejsze|Najnowsze|Wszystkie komentarze|Most relevant|All comments)$/i.test(t)){
          const y=e.getBoundingClientRect().top; if(y>0&&y<commentsTop) commentsTop=y;
        }
      }
      // Post body = the top-most substantial dir=auto text blocks ABOVE the
      // comments. This excludes nav noise AND every comment (so a commenter named
      // "… Szczupak" or a diet post's fish list can't fake topical relevance).
      let blocks=[...dlg.querySelectorAll('[dir="auto"]')]
        .map(e=>({t:(e.innerText||'').replace(/\s+/g,' ').trim(), y:e.getBoundingClientRect().top}))
        .filter(o=>o.t.length>25 && o.y<commentsTop)
        .sort((a,b)=>a.y-b.y);
      const seen=new Set(); const picked=[];
      for(const b of blocks){
        if(seen.has(b.t)) continue;
        if([...seen].some(s=>s.includes(b.t)||b.t.includes(s))) continue;
        seen.add(b.t); picked.push(b.t); if(picked.length>=3) break;
      }
      const body=picked.join(' | ');
      const low=body.toLowerCase();
      const hits=topic.filter(k=>k && low.includes(k));
      return JSON.stringify({url:location.href, bodyLen:body.length,
        body:body.slice(0,400), hits});
    })(''' + cfg + r''')''')


def close_dialog():
    # Return to the search feed by closing any open post dialog.
    try:
        press_key('Escape')
    except Exception:
        pass
    time.sleep(2)


def post_id_from_url(url):
    # Stable per-post id for cross-run dedup (so we never comment twice on the
    # same post, even for different articles).
    import re
    for pat in (r'pfbid[0-9A-Za-z]+', r'story_fbid=(\d+)', r'/posts/(\d+)',
                r'/videos/(\d+)', r'/(\d{6,})(?:[/?]|$)'):
        m = re.search(pat, url or '')
        if m:
            return m.group(0) if pat.startswith('pfbid') else m.group(1)
    return (url or '').split('?')[0]


def article_already_promoted(url):
    # Dedup gate, run with the post dialog OPEN. Returns True if this exact
    # article URL (or its slug) already appears in the open post — i.e. FishPoint
    # has already promoted it here, so we must NOT comment again. Scans the
    # dialog (or whole document as a fallback) for the article link/slug.
    slug = url.rstrip('/').split('/')[-1]
    cfg = json.dumps({'url': url, 'slug': slug})
    res = js(r'''((cfg)=>{
      const {url, slug}=cfg;
      const scope=document.querySelector('div[role="dialog"]') || document.body;
      const txt=(scope.innerText||'');
      // Normalised compare: FB strips dots from displayed links (fish-pointpl),
      // so match on the slug, which is stable, plus the raw url when present.
      const norm=s=>s.replace(/\s+/g,'').toLowerCase();
      const hay=norm(txt);
      const needle=norm(slug);
      const hrefHit=[...scope.querySelectorAll('a[href]')]
        .some(a=>(a.getAttribute('href')||'').includes(slug));
      return (needle && hay.includes(needle)) || hrefHit;
    })(''' + cfg + r''')''')
    return bool(res)


def debug_targets():
    # Diagnostic: dump the top scored cards and WHY each was/ wasn't eligible, so
    # a "no-target" run is explainable instead of silent.
    cfg = json.dumps({'minComments': min_comments, 'maxAgeHours': max_age_hours, 'minReactions': min_reactions, 'seen': sorted(seen)})
    return js(r'''((cfg)=>{''' + CARD_JS + r'''
      const cards=[...document.querySelectorAll('div[role="feed"] > div')].map(scoreCard)
        .filter(c=>c && c.visible).sort((a,b)=>b.score-a.score).slice(0,6);
      return cards.map(c=>{
        const why=[];
        if(c.ours) why.push('ours');
        if(!c.el) why.push('no-comment-button');
        if(c.seenBefore) why.push('seen');
        if(c.comments<minComments) why.push('comments<'+minComments);
        if(!(c.reactions>=minReactions || c.comments>=minComments*3)) why.push('reactions<'+minReactions);
        if(!(c.age===null || c.age<=maxAgeHours)) why.push('too-old');
        return 'react='+c.reactions+' com='+c.comments+' sh='+c.shares
          +' age='+(c.age===null?'?':c.age.toFixed(1)+'h')+(c.verified?' verified':'')
          +' score='+Math.round(c.score)+' '+(why.length?('REJECT['+why.join(',')+']'):'OK');
      });
    })(''' + cfg + r''')''')


def find_editor():
    return js(r'''(()=>{
      const els=Array.from(document.querySelectorAll('[contenteditable="true"], div[role="textbox"]')).map(e=>{
        const r=e.getBoundingClientRect();
        return {txt:(e.innerText||'').trim(), a:e.getAttribute('aria-label')||'', x:r.x, y:r.y, w:r.width, h:r.height};
      }).filter(o=>o.w>30&&o.h>12&&o.y>150&&o.y<930)
        .sort((a,b)=>b.y-a.y);
      if(!els.length) return null;
      const b=els[0]; return [b.x+b.w/2,b.y+b.h/2,b.a,b.txt];
    })()''')


def click_editor_near(pos):
    candidates = []
    if pos:
        x,y = float(pos[0]), float(pos[1])
        candidates += [(x+40,y), (x+160,y), (x+220,y+35), (960,850), (930,790), (1180,790)]
    else:
        candidates += [(960,850), (930,790), (1180,790)]
    for x,y in candidates:
        click_at_xy(x,y); time.sleep(1)
        ed = find_editor()
        if ed:
            click_at_xy(float(ed[0]), float(ed[1]))
            time.sleep(.5)
            return ed
    return None


def click_send_button():
    # Click the comment composer's SEND control via a real DOM .click() (more
    # reliable than coordinate clicks). Pick a visible, NOT-disabled button whose
    # aria-label means "send/comment", lowest on the page (the composer bar).
    res = js(r'''(()=>{
      // The comment SEND control (paper-plane). In PL FB its aria-label is
      // exactly "Komentarz" / "Skomentuj"; EN "Comment"/"Reply". Must EXCLUDE
      // unrelated controls that also contain "wyślij" — the share button
      // ("Wyślij do znajomych…"), Messenger, etc.
      const ok=/^komentarz$|^skomentuj$|^comment$|^odpowiedz$|^reply$|wyślij komentarz|post comment/i;
      const bad=/znajom|profil|messenger|udost|share|prześlij|wątek|story|relacj/i;
      const btns=[...document.querySelectorAll('[role="button"],button,div[aria-label]')]
        .filter(e=>{
          const a=(e.getAttribute('aria-label')||'').trim();
          if(!ok.test(a) || bad.test(a)) return false;
          if(e.getAttribute('aria-disabled')==='true' || e.disabled) return false;
          const r=e.getBoundingClientRect();
          return r.width>0 && r.height>0 && r.top>300;
        })
        .sort((a,b)=>b.getBoundingClientRect().top-a.getBoundingClientRect().top);
      if(!btns.length) return null;
      btns[0].scrollIntoView({block:'center'});
      btns[0].click();
      return btns[0].getAttribute('aria-label')||'sent';
    })()''')
    if res:
        print(f'[fejs-komcie] send button clicked: {res}')
        return True
    return False


def comment_state(comment):
    # Decide whether our comment is (a) still sitting in the editor -> 'in-editor',
    # (b) posted and visible on the page -> 'posted', or (c) gone -> 'gone'.
    frag = comment[:50]
    cfg = json.dumps({'frag': frag})
    return js(r'''((cfg)=>{
      const {frag}=cfg;
      const inEditor=[...document.querySelectorAll('[contenteditable="true"],div[role="textbox"]')]
        .some(e=>(e.innerText||'').includes(frag));
      if(inEditor) return 'in-editor';
      const onPage=(document.body.innerText||'').includes(frag);
      return onPage ? 'posted' : 'gone';
    })(''' + cfg + r''')''')


def focus_editor():
    # Re-focus the comment composer. FB frequently steals focus to the link
    # unfurl preview after typing, which makes a plain Enter do nothing — so we
    # re-locate and click the editor right before every send attempt.
    ed = find_editor()
    if ed:
        click_at_xy(float(ed[0]), float(ed[1]))
        time.sleep(.6)
    return ed


def type_char_once(ch):
    # Insert a SINGLE printable char with real key events. We deliberately do NOT
    # call the harness's press_key() here: for a printable char it dispatches
    # BOTH a keyDown carrying text AND a separate char event, and FB's Lexical
    # editor inserts the character on each -- so every letter comes out doubled
    # ("JJaakk wwyy"). A keyDown-with-text plus keyUp inserts the char exactly
    # once while still firing the key listeners Lexical needs to enable sending.
    vk = ord(ch)
    base = {'key': ch, 'code': '', 'modifiers': 0,
            'windowsVirtualKeyCode': vk, 'nativeVirtualKeyCode': vk}
    cdp('Input.dispatchKeyEvent', type='keyDown', text=ch, **base)
    cdp('Input.dispatchKeyEvent', type='keyUp', **base)


def type_real(text):
    # Type with REAL key events so FB's React/Lexical editor registers each
    # character and enables sending. type_text() uses Input.insertText, which
    # bypasses framework listeners — the text shows up in the DOM but the
    # composer's state stays "empty", so Enter/Send do nothing.
    for ch in text:
        if ch == '\n':
            continue
        type_char_once(ch)


def submit_comment(comment):
    ed = focus_editor()
    if not ed:
        return False
    time.sleep(.5)
    type_real(comment)
    # Let the link preview/url unfurl and editor state settle before sending.
    time.sleep(3)
    # FIRST try Enter while the caret is still in the editor (don't refocus —
    # a stray click could blur or open the link preview). Lexical submits a
    # comment on Enter once it has registered real keystrokes.
    press_key('Enter')
    time.sleep(3)
    # Then alternate the explicit comment-send button and a refocused Enter.
    # Never report success unless the comment is actually visible on the page.
    for attempt in range(8):
        if comment_state(comment) == 'posted':
            return True
        if click_send_button():
            time.sleep(4)
            continue
        focus_editor()
        press_key('Enter')
        time.sleep(4)
    # Final settle window for slow publishing.
    deadline = time.time() + 25
    while time.time() < deadline:
        if comment_state(comment) == 'posted':
            return True
        time.sleep(3)
    print(f'[fejs-komcie] NOT confirmed posted; last state={comment_state(comment)}')
    return False


# How many of the top search results to try before giving up on an article.
MAX_POSTS_TRIED = 6


def comment_once(item, idx):
    # Open the top results one by one and, for EACH, VERIFY before commenting:
    #   1) WHERE — judge relevance on the opened post's OWN body (inspect_post);
    #      an off-topic post (e.g. dresses) is closed and skipped.
    #   2) NO REPEAT — skip posts we've already commented under (post id in seen,
    #      across runs) and posts that already contain this article's link.
    #   3) WHAT — only then type the comment, and only confirm success if the
    #      comment is actually visible (submit_comment verifies).
    # Move to the next result when a post fails any check; stop at the first that
    # passes. Better to comment nowhere than under the wrong post.
    global seen
    topic = item.get('topic') or []
    new_tab(item['search'])
    try:
        wait_for_load()
    except Exception:
        pass
    time.sleep(6)
    for n in range(MAX_POSTS_TRIED):
        close_dialog()  # make sure we're on the feed before opening result #n
        op = js_retry(lambda: open_nth_post(n), tries=2)
        if op != 'opened':
            print(f'[fejs-komcie] {idx}: no more results at #{n} ({op})')
            break
        time.sleep(5)
        raw = js_retry(lambda: inspect_post(topic), tries=4, wait=3)
        if not raw:
            print(f'[fejs-komcie] {idx} post#{n}: dialog did not open; skipping')
            close_dialog()
            continue
        info = json.loads(raw)
        pid = post_id_from_url(info.get('url', ''))
        body = info.get('body', '')
        hits = info.get('hits', [])
        print(f'[fejs-komcie] {idx} post#{n}: id={pid} hits={hits[:6]} body="{body[:120]}"')
        # NO REPEAT: same post already commented on (any earlier run/article).
        if pid in seen:
            print(f'[fejs-komcie] {idx} post#{n}: already commented under this post — next')
            close_dialog()
            continue
        # WHERE: post body must be on-topic (skip off-topic placement).
        if topic and not hits:
            print(f'[fejs-komcie] {idx} post#{n}: OFF-TOPIC (no fishing keyword in post body) — next')
            shot(f'off-topic-{idx}-{n}')
            close_dialog()
            continue
        # NO REPEAT (per article): this article's link is already under this post.
        if article_already_promoted(item['url']):
            print(f'[fejs-komcie] {idx} post#{n}: article already promoted here — next')
            close_dialog()
            continue
        ed = js_retry(find_editor, tries=6, wait=3)
        if not ed:
            print(f'[fejs-komcie] {idx} post#{n}: no composer — next')
            close_dialog()
            continue
        click_at_xy(float(ed[0]), float(ed[1]))
        time.sleep(1)
        # Last line of defence: re-assert identity with the composer open.
        assert_page_identity(f'composer-{idx}-{n}')
        ok = submit_comment(item['comment'])
        shot(f'after-submit-{idx}-{n}')
        print(f'[fejs-komcie] {idx} post#{n}: submitted={ok} (where=id:{pid})')
        if ok:
            seen.add(pid)
            save_seen(seen)
            shot(f'verified-success-{idx}')
            return True
        # Posting failed on this post — try the next one.
        close_dialog()
    print(f'[fejs-komcie] {idx}: no suitable on-topic post found in first {MAX_POSTS_TRIED} results')
    return False

def collect_candidates(item, idx):
    # READ-ONLY: open the top results for an article and return each candidate
    # post's body + permalink so an external judge (the agent) can decide WHERE
    # it is appropriate to comment. Never types anything.
    new_tab(item['search'])
    try:
        wait_for_load()
    except Exception:
        pass
    time.sleep(6)
    cands = []
    for n in range(MAX_POSTS_TRIED):
        close_dialog()
        op = js_retry(lambda: open_nth_post(n), tries=2)
        if op != 'opened':
            break
        time.sleep(5)
        raw = js_retry(lambda: inspect_post(item.get('topic') or []), tries=4, wait=3)
        if not raw:
            close_dialog()
            continue
        info = json.loads(raw)
        url = info.get('url', '')
        pid = post_id_from_url(url)
        cands.append({
            'n': n,
            'postUrl': url,
            'postId': pid,
            'body': info.get('body', ''),
            'keywordHits': info.get('hits', []),
            'alreadyCommented': pid in seen,
            'articleAlreadyPromoted': bool(article_already_promoted(item['url'])),
        })
    close_dialog()
    return cands


def post_to_decision(dec, idx):
    # Comment on a SPECIFIC post chosen by the judge. Re-checks dedup (post id +
    # article-already-promoted) right before posting, then verifies the comment
    # is visible. dec = {postUrl, comment, postId, url(article)}.
    global seen
    pid = dec.get('postId') or post_id_from_url(dec.get('postUrl', ''))
    if pid in seen:
        print(f'[fejs-komcie] {idx}: post {pid} already commented — skip')
        return False
    new_tab(dec['postUrl'])
    try:
        wait_for_load()
    except Exception:
        pass
    time.sleep(6)
    if article_already_promoted(dec.get('url') or dec.get('postUrl')):
        print(f'[fejs-komcie] {idx}: article already promoted under {pid} — skip')
        return False
    ed = js_retry(find_editor, tries=6, wait=3)
    if not ed:
        print(f'[fejs-komcie] {idx}: no composer on {dec["postUrl"]}')
        shot(f'no-editor-decision-{idx}')
        return False
    click_at_xy(float(ed[0]), float(ed[1]))
    time.sleep(1)
    assert_page_identity(f'decision-{idx}')
    ok = submit_comment(dec['comment'])
    shot(f'decision-after-{idx}')
    print(f'[fejs-komcie] {idx}: posted={ok} where={pid} url={dec["postUrl"]}')
    if ok:
        seen.add(pid)
        save_seen(seen)
    return ok


MODE = __MODE__
DECISIONS = __DECISIONS__

if MODE == 'collect':
    # No identity gate needed — we never post in this phase.
    out = []
    for i, item in enumerate(items, 1):
        try:
            cands = collect_candidates(item, i)
        except Exception as e:
            print(f'[fejs-komcie] collect error on {i}: {e}')
            cands = []
        out.append({'slug': item.get('slug'), 'url': item['url'],
                    'comment': item['comment'], 'candidates': cands})
    print('FEJS_COLLECT_JSON ' + json.dumps(out, ensure_ascii=False))
elif MODE == 'post':
    posted = 0
    preflight_identity()
    for i, dec in enumerate(DECISIONS, 1):
        try:
            if post_to_decision(dec, i):
                posted += 1
        except WrongIdentity as e:
            print(f'[fejs-komcie] ABORT: {e}')
            raise
        except Exception as e:
            print(f'[fejs-komcie] error on {i}: {e}')
            shot(f'error-decision-{i}')
        time.sleep(delay_ms/1000)
    print(f'[fejs-komcie] done verified={posted} planned={len(DECISIONS)}')
else:
    posted=0
    completed = [False] * len(items)
    # Verify acting identity ONCE up front; abort the whole run if it is wrong.
    preflight_identity()
    for attempt in range(1, max_attempts + 1):
        print(f'[fejs-komcie] pass {attempt}/{max_attempts}; posted={posted}; target={min_success}')
        for i,item in enumerate(items,1):
            if completed[i-1]:
                continue
            try:
                if comment_once(item,i):
                    completed[i-1] = True
                    posted += 1
                    shot(f'verified-success-{i}')
            except WrongIdentity as e:
                # Never publish from the wrong account — stop everything immediately.
                print(f'[fejs-komcie] ABORT: {e}')
                raise
            except Exception as e:
                print(f'[fejs-komcie] error on {i}: {e}')
                shot(f'error-{i}')
            if min_success and posted >= min_success:
                break
            time.sleep(delay_ms/1000)
        if min_success and posted >= min_success:
            break
        if not min_success:
            break  # single pass when no success quota was requested
    print(f'[fejs-komcie] done verified={posted} planned={len(items)} min_success={min_success}')
    if posted < min_success:
        raise RuntimeError(f'Only verified {posted}/{min_success} required Facebook comments')
`;

const mode = process.argv.includes('--collect') ? 'collect'
  : (process.argv.find(a => a.startsWith('--decisions=')) ? 'post' : 'auto');
let decisions = [];
if (mode === 'post') {
  const decPath = process.argv.find(a => a.startsWith('--decisions=')).split('=')[1];
  decisions = JSON.parse(readFileSync(decPath, 'utf8'));
}

runHarness(py
  .replace('__ITEMS__', JSON.stringify(selected))
  .replace('__DELAY_MS__', String(delayMs))
  .replace('__MIN_SUCCESS__', String(minSuccess))
  .replace('__MAX_ATTEMPTS__', String(maxAttempts))
  .replace('__MIN_COMMENTS__', String(minComments))
  .replace('__MAX_AGE_HOURS__', String(maxAgeHours))
  .replace('__MIN_REACTIONS__', String(minReactions))
  .replace('__MODE__', JSON.stringify(mode))
  .replace('__DECISIONS__', JSON.stringify(decisions)));
