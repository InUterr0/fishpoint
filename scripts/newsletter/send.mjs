// Wysyłka newslettera FishPoint — czyta subskrybentów z tabeli
// `fishpoint_subscribers` (izolowanej od GlobBrief), bierze najnowsze wpisy z
// fish-point.pl/feed.xml, wysyła digest przez Resend i zapamiętuje wysłane
// artykuły w `fishpoint_newsletter_sent`, żeby nie dublować.
//
// Uruchamiane z GitHub Actions (.github/workflows/newsletter.yml).
// Wymagane sekrety: DATABASE_URL (publiczny URL bazy Railway),
//   RESEND_API_KEY, FISHPOINT_NEWSLETTER_FROM.
// DRY_RUN=1 => nie wysyła i nie zapisuje, tylko loguje.
import pg from 'pg';

const DRY = process.env.DRY_RUN === '1' || process.env.DRY_RUN === 'true';
const FROM = process.env.FISHPOINT_NEWSLETTER_FROM || 'FishPoint <newsletter@fish-point.pl>';
const FEED_URL = process.env.FEED_URL || 'https://fish-point.pl/feed.xml';
const UNSUB_BASE = 'https://globbrief.com/api/fishpoint-unsubscribe';
const MAX_ITEMS = Number(process.env.MAX_ITEMS || 6);
const SITE = 'https://fish-point.pl';

const log = (...a) => console.log('[fp-newsletter]', ...a);

const decode = (s) => String(s || '')
  .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
  .replace(/&amp;/g, '&').trim();

function parseFeed(xml) {
  const items = [];
  const re = /<item\b[\s\S]*?<\/item>/gi;
  let m;
  while ((m = re.exec(xml))) {
    const block = m[0];
    const pick = (tag) => {
      const r = new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i').exec(block);
      return r ? decode(r[1]) : '';
    };
    items.push({ title: pick('title'), link: pick('link'), description: pick('description'), pubDate: pick('pubDate') });
  }
  return items;
}

async function ensureTables(client) {
  await client.query(`CREATE TABLE IF NOT EXISTS fishpoint_subscribers (
    id SERIAL PRIMARY KEY, email TEXT NOT NULL UNIQUE, token TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), unsubscribed_at TIMESTAMPTZ)`);
  await client.query(`CREATE TABLE IF NOT EXISTS fishpoint_newsletter_sent (
    url TEXT PRIMARY KEY, sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`);
}

function emailHtml(items, unsubUrl) {
  const dateStr = new Date().toISOString().slice(0, 10);
  const rows = items.map((p) =>
    `<tr><td style="padding:0 0 18px"><a href="${p.link}" style="color:#0e3b36;font-size:17px;font-weight:700;text-decoration:none">${p.title}</a><br>` +
    `<span style="color:#4b5b58;font-size:14px">${(p.description || '').slice(0, 180)}</span></td></tr>`).join('');
  return `<!doctype html><html><body style="margin:0;background:#eef4f2;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:28px 14px">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border-radius:12px;padding:28px">
<tr><td style="padding-bottom:18px"><a href="${SITE}/" style="font-size:21px;font-weight:800;color:#0e5e54;text-decoration:none">Fish<span style="color:#2ba798">Point</span></a><br><span style="color:#4b5b58;font-size:13px">Najnowsze poradniki i brania · ${dateStr}</span></td></tr>
${rows}
<tr><td style="border-top:1px solid #e2e8e6;padding-top:14px;color:#94a3a0;font-size:12px">Dostajesz tego maila, bo zapisałeś(-aś) się na fish-point.pl.<br><a href="${unsubUrl}" style="color:#94a3a0">Wypisz się</a></td></tr>
</table></td></tr></table></body></html>`;
}

async function main() {
  if (!process.env.DATABASE_URL) { log('DATABASE_URL missing — abort'); process.exit(1); }
  const client = new pg.Client({ connectionString: process.env.DATABASE_URL, ssl: { rejectUnauthorized: false } });
  await client.connect();
  try {
    await ensureTables(client);
    const res = await fetch(FEED_URL, { headers: { 'User-Agent': 'FishPoint-Newsletter' } });
    if (!res.ok) { log(`feed HTTP ${res.status} — abort`); return; }
    const all = parseFeed(await res.text());
    if (!all.length) { log('feed: 0 items — abort'); return; }
    // najnowsze najpierw
    all.sort((a, b) => (Date.parse(b.pubDate) || 0) - (Date.parse(a.pubDate) || 0));

    const sentRows = await client.query('SELECT url FROM fishpoint_newsletter_sent');
    const sent = new Set(sentRows.rows.map((r) => r.url));
    const fresh = all.filter((it) => it.link && !sent.has(it.link)).slice(0, MAX_ITEMS);
    if (!fresh.length) { log('brak nowych wpisów'); return; }
    log(`nowych wpisów: ${fresh.length}`, fresh.map((f) => f.link));

    const subs = (await client.query('SELECT email, token FROM fishpoint_subscribers WHERE unsubscribed_at IS NULL')).rows;
    log(`aktywni subskrybenci: ${subs.length}`);

    if (DRY) { log('DRY_RUN — bez wysyłki i zapisu. FROM =', FROM, '| przykład:', subs[0]?.email || '(brak)'); return; }

    let sentCount = 0;
    if (subs.length) {
      if (!process.env.RESEND_API_KEY) { log('RESEND_API_KEY missing — abort'); return; }
      const subject = fresh.length === 1 ? `FishPoint: ${fresh[0].title}` : `FishPoint: ${fresh.length} nowe poradniki znad wody`;
      const emails = subs.map((s) => ({
        from: FROM, to: [s.email], subject,
        html: emailHtml(fresh, `${UNSUB_BASE}?token=${s.token}`),
        headers: { 'List-Unsubscribe': `<${UNSUB_BASE}?token=${s.token}>` },
      }));
      for (let i = 0; i < emails.length; i += 100) {
        const r = await fetch('https://api.resend.com/emails/batch', {
          method: 'POST',
          headers: { Authorization: `Bearer ${process.env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
          body: JSON.stringify(emails.slice(i, i + 100)),
        });
        if (!r.ok) log(`batch HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
        else sentCount += Math.min(100, emails.length - i);
      }
      log(`wysłano: ${sentCount}/${subs.length}`);
    } else {
      log('0 subskrybentów — oznaczam wpisy jako wysłane, by nie zalegały');
    }
    for (const it of fresh) {
      await client.query('INSERT INTO fishpoint_newsletter_sent (url) VALUES ($1) ON CONFLICT (url) DO NOTHING', [it.link]);
    }
    log('gotowe.');
  } finally {
    await client.end();
  }
}

main().catch((e) => { console.error('[fp-newsletter] fatal:', e.message); process.exit(1); });
