#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { latestArticles } from '../lib/latest-articles.mjs';

// Targets are built live from the freshest published articles (featured first).
// Use --latest=N to widen the candidate pool.
const latestArg = process.argv.find(a => a.startsWith('--latest='));
const poolSize = Number(latestArg?.split('=')[1] || 8);
const pool = latestArticles(process.cwd(), poolSize).map(a => ({
  slug: a.slug,
  search: `https://www.facebook.com/search/posts?q=${encodeURIComponent(a.query)}`,
  comment: `${a.note} Więcej: ${a.url}`,
}));

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


def preflight_identity():
    # Open FB home once and assert the session is acting as the Page before any
    # commenting begins. Aborts the run on a wrong/unconfirmed identity.
    new_tab('https://www.facebook.com/')
    try:
        wait_for_load()
    except Exception as e:
        print(f'[fejs-komcie] home nav slow ({e}); checking anyway')
    time.sleep(5)
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


def first_comment_target():
    # DEAD SIMPLE: comment under the FIRST post in the results. Find every
    # "Comment/Skomentuj" action button on the page, take the TOP-MOST one
    # (that's the first post), and click it to open the composer. No scoring,
    # no thresholds, no engagement parsing, no dedup — just the first post shown.
    return js(r'''(()=>{
      function isComment(el){
        const a=(el.getAttribute('aria-label')||'').toLowerCase().trim();
        if(!a) return false;
        // Match the comment ACTION (write), not "see N comments" preview links.
        return /^skomentuj$|^komentarz$|napisz komentarz|leave a comment|^comment$|write a comment/.test(a);
      }
      let cands=[...document.querySelectorAll('[role="button"],[aria-label]')]
        .filter(el=>{
          if(!isComment(el)) return false;
          const r=el.getBoundingClientRect();
          return r.width>0 && r.height>0 && r.top>140; // skip the top nav bar
        });
      // Fallback: if no explicit "Skomentuj" button matched, use any clickable
      // whose aria-label merely mentions a comment.
      if(!cands.length){
        cands=[...document.querySelectorAll('[role="button"],[aria-label],a')]
          .filter(el=>{
            const a=(el.getAttribute('aria-label')||'').toLowerCase();
            const r=el.getBoundingClientRect();
            return /komentarz|comment/.test(a) && r.width>0 && r.height>0 && r.top>140;
          });
      }
      if(!cands.length) return null;
      cands.sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top);
      const b=cands[0];
      b.scrollIntoView({block:'center'});
      b.click();
      const card=b.closest('div[role="article"]') || b.closest('div[role="feed"] > div');
      const info=(card?card.innerText:'').replace(/\s+/g,' ').trim().slice(0,180);
      return ['comment-click', 0, info, '', 0, null, null];
    })()''')


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
    # Click the comment composer's SEND button (the blue arrow). Returns True if
    # a send control was found and clicked. We pick a visible control low on the
    # page (composer area) whose aria-label means "send/comment", rightmost first.
    pos = js(r'''(()=>{
      const re=/^komentarz$|wyślij|^comment$|^post$|^send$|opublikuj/i;
      const btns=[...document.querySelectorAll('[role="button"],button,[aria-label]')]
        .filter(e=>{
          const a=(e.getAttribute('aria-label')||'').trim();
          const r=e.getBoundingClientRect();
          return re.test(a) && r.width>0 && r.height>0 && r.top>500;
        })
        .map(e=>{const r=e.getBoundingClientRect();return [r.x+r.width/2, r.y+r.height/2, r.x];})
        .sort((a,b)=>b[2]-a[2]);
      return btns.length? [btns[0][0], btns[0][1]] : null;
    })()''')
    if pos:
        click_at_xy(float(pos[0]), float(pos[1]))
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


def submit_comment(comment):
    type_text(comment)
    # Let the link preview/url unfurl settle before sending.
    time.sleep(3)
    # Try Enter first, then explicitly click the send button if the text is still
    # sitting in the editor. Repeat a few times — never report success unless the
    # comment actually left the editor and is visible on the page.
    for attempt in range(4):
        st = comment_state(comment)
        if st == 'posted':
            return True
        if st == 'in-editor':
            if attempt == 0:
                press_key('Enter')
            else:
                if not click_send_button():
                    press_key('Enter')
        time.sleep(3)
    # Final settle window for slow publishing.
    deadline = time.time() + 20
    while time.time() < deadline:
        if comment_state(comment) == 'posted':
            return True
        time.sleep(3)
    print(f'[fejs-komcie] NOT confirmed posted; last state={comment_state(comment)}')
    return False


def comment_once(item, idx):
    new_tab(item['search'])
    try:
        wait_for_load()
    except Exception:
        pass
    time.sleep(6)
    # SIMPLE RULE: comment under the FIRST post shown. DO NOT scroll the feed —
    # just wait for the top result to render and take it. Retry in place only to
    # ride out a slow render, never to move down the page.
    pos = None
    for _ in range(5):
        pos = js_retry(first_comment_target, tries=2)
        if pos:
            break
        time.sleep(2)
    print(f'[fejs-komcie] comment target {idx}: {pos}')
    if not pos:
        shot(f'no-target-{idx}')
        return False
    # The picker already DOM-clicked the comment count; wait for the post
    # dialog to render, then locate its composer (with busy-page retries).
    time.sleep(5)
    ed = js_retry(find_editor, tries=6, wait=3)
    print(f'[fejs-komcie] editor {idx}: {ed}')
    if not ed:
        shot(f'no-editor-{idx}')
        return False
    click_at_xy(float(ed[0]), float(ed[1]))
    time.sleep(1)
    # Last line of defence: re-assert identity with the comment composer open,
    # so we never type as a personal account even if FB switched mid-run.
    assert_page_identity(f'composer-{idx}')
    ok = submit_comment(item['comment'])
    shot(f'after-submit-{idx}')
    print(f'[fejs-komcie] submitted {idx}: {ok}')
    if ok:
        # Persist the post id + signature so future runs skip this post.
        global seen
        for key in (pos[5] if len(pos) > 5 else None, pos[6] if len(pos) > 6 else None):
            if key:
                seen.add(key)
        save_seen(seen)
    return ok

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

runHarness(py
  .replace('__ITEMS__', JSON.stringify(selected))
  .replace('__DELAY_MS__', String(delayMs))
  .replace('__MIN_SUCCESS__', String(minSuccess))
  .replace('__MAX_ATTEMPTS__', String(maxAttempts))
  .replace('__MIN_COMMENTS__', String(minComments))
  .replace('__MAX_AGE_HOURS__', String(maxAgeHours))
  .replace('__MIN_REACTIONS__', String(minReactions)));
