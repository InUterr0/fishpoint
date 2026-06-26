#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { latestArticles } from '../lib/latest-articles.mjs';
import { FB } from '../lib/fb-config.mjs';

// Cele budowane na żywo z najświeższych artykułów. --latest=N poszerza pulę.
const latestArg = process.argv.find(a => a.startsWith('--latest='));
const poolSize = Number(latestArg?.split('=')[1] || 8);
const pool = latestArticles(process.cwd(), poolSize).map(a => ({
  slug: a.slug,
  search: `https://www.facebook.com/search/posts?q=${encodeURIComponent(a.query)}`,
  comment: `${a.note}\n\nWięcej: ${a.url}`,
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
PAGE_NAME = __PAGE_NAME__


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
PAGE_ID = __PAGE_ID__
# Prywatne konta, z których komentarze NIGDY nie mają wychodzić. Jeśli aktywną
# tożsamością FB jest któreś z nich, cały run jest przerywany przed publikacją.
BAD_ACCOUNTS = __BAD_ACCOUNTS__


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
    # HARD GATE. Confirm we are acting as the news Page and NOT a personal
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
    print('[fejs-komcie] preflight identity OK — acting as the news Page')


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


def first_comment_target():
    # FB search results render each post as div[role="feed"] > div, ending with
    # three bare numbers: reactions | comments | shares. We want the BEST
    # placement, not just the loudest post: a comment is only worth posting if
    # the thread is (a) still alive (recent), (b) reaches a real audience (high
    # reactions / big or verified page) and (c) actively discussed (so our
    # comment is seen). Score blends reach + freshness + page authority.
    cfg = json.dumps({'minComments': min_comments, 'maxAgeHours': max_age_hours, 'minReactions': min_reactions, 'seen': sorted(seen)})
    return js(r'''((cfg)=>{
      const {minComments, maxAgeHours, minReactions, seen} = cfg;
      const seenSet = new Set(seen);
      // Stable id for a search-result card, so we never comment under the same
      // post twice across runs. Falls back to a content signature when no
      // permalink can be extracted.
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
      function nval(s){
        s=(s||'').replace(/\s/g,'');
        const m=s.match(/^(\d+[.,]?\d*)(tys\.?|mln|[KkMm])?$/);
        if(!m) return null;
        let n=parseFloat(m[1].replace(',','.'));
        if(m[2]){ if(/tys|[Kk]/.test(m[2])) n*=1000; else n*=1000000; }
        return n;
      }
      // Parse a post's age (hours) from its relative timestamp. Handles PL/EN:
      // "5 godz.", "2 g", "23 min", "1 dzień", "Wczoraj", "5h", "2d", "Just now".
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
      const cards=[...document.querySelectorAll('div[role="feed"] > div')]
        .map((card)=>{
          const r=card.getBoundingClientRect();
          const lines=(card.innerText||'').split('\n').map(x=>x.trim()).filter(x=>x && x!=='Facebook');
          const tail=lines.slice(-6).map(nval).filter(v=>v!==null);
          if(tail.length<2) return null;
          const [reactions, comments, shares=0] = tail.slice(-3).length===3 ? tail.slice(-3) : [tail[0], tail[1], 0];
          const ours=new RegExp('fish-point\\.com|fish-point\\.pl|'+__PAGE_NAME_RE__,'i').test(card.innerText||'');
          const age=ageHours(card);
          // Verified / large page = bigger reach and a more credible context.
          const verified=!!card.querySelector('svg[aria-label*="erified"], svg[aria-label*="weryfik"], [aria-label*="Zweryfikowane"], [aria-label*="Verified account"]');
          // The comment count span is the clickable way into the post's comment box.
          const target=[...card.querySelectorAll('span')].find(e=>{
            const v=nval((e.innerText||'').trim());
            return v===comments && e.getBoundingClientRect().width>0;
          });
          // Freshness multiplier: a post at age 0 scores ~2x, decaying to 1x at
          // the max age; unknown age is treated as borderline (0.85).
          const fresh = age===null ? 0.85 : Math.max(0.2, 1 + (maxAgeHours - age)/maxAgeHours);
          const reach = comments*4 + reactions + shares*6;
          const pid=postId(card); const psig=sig(card);
          return {reactions, comments, shares, ours, age, verified, el: target || null,
            pid, psig, seenBefore: seenSet.has(pid) || seenSet.has(psig),
            score: reach * fresh * (verified?1.35:1),
            visible: r.height>120};
        })
        .filter(c=>c && c.visible && !c.ours && c.el)
        // Skip posts we've already commented under (persistent dedup).
        .filter(c=>!c.seenBefore)
        // Hard gates: enough discussion, real reach, and not stale.
        .filter(c=>c.comments>=minComments && (c.reactions>=minReactions || c.comments>=minComments*3))
        .filter(c=>c.age===null || c.age<=maxAgeHours)
        .sort((a,b)=>b.score-a.score);
      if(!cards.length) return null;
      const p=cards[0];
      const clickable=p.el.closest('a,[role="button"]')||p.el;
      clickable.scrollIntoView({block:'center'});
      clickable.click();
      const ageStr = p.age===null ? 'age=?' : ('age='+p.age.toFixed(1)+'h');
      return ['dom-click', 0, 'reactions='+p.reactions+' comments='+p.comments+' shares='+p.shares+' '+ageStr+(p.verified?' verified':''), '', Math.round(p.score), p.pid, p.psig];
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


def submit_comment(comment):
    type_text(comment)
    time.sleep(1)
    press_key('Enter')
    # Verify until Facebook finishes publishing and the exact comment is visible as a posted comment,
    # not only text left in the editor.
    deadline = time.time() + 35
    last = ''
    while time.time() < deadline:
        time.sleep(3)
        txt = body_text()
        last = txt
        if 'Publikowanie' in txt or 'Publishing' in txt:
            continue
        if ('fish-point.pl' in txt and comment[:45] in txt and ('Odpowiedz' in txt or 'Reply' in txt or 'Lubię to!' in txt)):
            return True
    print('[fejs-komcie] verification text tail:', last[-1000:])
    return False


def comment_once(item, idx):
    new_tab(item['search'])
    try:
        wait_for_load()
    except Exception:
        pass
    time.sleep(6)
    # Scroll through the results to surface high-engagement posts before picking.
    pos = js_retry(first_comment_target)
    for _ in range(4):
        if pos:
            break
        try:
            scroll(960, 500, dy=700)
        except Exception:
            pass
        time.sleep(2)
        pos = js_retry(first_comment_target, tries=2)
    print(f'[fejs-komcie] comment target {idx}: {pos} min_comments={min_comments}')
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

// Escapowana nazwa strony do regexa wykrywającego nasze własne posty.
const pageNameRe = JSON.stringify(
  FB.PAGE_NAME.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
);

runHarness(py
  .replace('__ITEMS__', JSON.stringify(selected))
  .replace('__DELAY_MS__', String(delayMs))
  .replace('__MIN_SUCCESS__', String(minSuccess))
  .replace('__MAX_ATTEMPTS__', String(maxAttempts))
  .replace('__PAGE_NAME__', JSON.stringify(FB.PAGE_NAME))
  .replace('__PAGE_NAME_RE__', pageNameRe)
  .replace('__PAGE_ID__', JSON.stringify(FB.PAGE_ID))
  .replace('__BAD_ACCOUNTS__', JSON.stringify(FB.BAD_ACCOUNTS))
  .replace('__MIN_COMMENTS__', String(minComments))
  .replace('__MAX_AGE_HOURS__', String(maxAgeHours))
  .replace('__MIN_REACTIONS__', String(minReactions)));
