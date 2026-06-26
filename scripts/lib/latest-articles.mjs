// Wspólne źródło promowanych artykułów dla skryptów X/Facebook/Google.
// Czyta najświeższe wpisy z aktualnosci/*.html (po dacie modyfikacji pliku),
// żeby skrypty nigdy się nie zestarzały — żadnych list na sztywno.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const SITE = 'https://fish-point.pl';

// Polskie słowa-wypełniacze: zawężają wyszukiwanie na X/FB nic nie wnosząc.
const STOPWORDS = new Set([
  'i', 'oraz', 'a', 'ale', 'lub', 'albo', 'czy', 'że', 'bo', 'na', 'w', 'we',
  'z', 'ze', 'do', 'od', 'po', 'za', 'o', 'u', 'przy', 'przez', 'dla', 'pod',
  'nad', 'jak', 'jako', 'to', 'co', 'się', 'jest', 'są', 'być', 'oraz', 'tu',
  'tym', 'ten', 'ta', 'te', 'już', 'tylko', 'nowy', 'nowa', 'nowe', 'sezon',
  'roku', 'rok', 'czyli', 'czym', 'gdy', 'kiedy', 'twoja', 'twój', 'swoje',
]);

// Wyciąga wartość pojedynczego tagu/atrybutu z surowego HTML.
function pick(html, re) {
  const m = html.match(re);
  return m ? m[1].trim() : '';
}

// Dekoduje najczęstsze encje HTML, żeby teksty postów wyglądały naturalnie.
function decode(s) {
  return s
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ')
    .replace(/&mdash;/g, '—').replace(/&ndash;/g, '–');
}

// Buduje zapytanie wyszukiwania z tytułu: zostawia 3 najmocniejsze słowa,
// bo X/FB łączą wszystkie tokeny przez AND.
function searchQueryFromTitle(title) {
  return title
    .replace(/[^\p{L}\p{N}\s-]/gu, ' ')
    .split(/\s+/)
    .filter(w => {
      if (!w || STOPWORDS.has(w.toLowerCase())) return false;
      if (/^\d+$/.test(w)) return false;
      if (w.length < 3) return false;
      return true;
    })
    .slice(0, 3)
    .join(' ');
}

/**
 * Zwraca najnowsze opublikowane artykuły (od najświeższego) jako:
 * { slug, url, title, description, query, note }
 */
export function latestArticles(root, limit = 10) {
  const dir = join(root, 'aktualnosci');
  const items = [];
  for (const file of readdirSync(dir)) {
    if (!file.endsWith('.html') || file === 'index.html') continue;
    const path = join(dir, file);
    const html = readFileSync(path, 'utf8');
    const slug = file.replace(/\.html$/, '');
    // Tytuł: <title> bez przyrostka serwisu „ — FishPoint".
    let title = decode(pick(html, /<title>([\s\S]*?)<\/title>/i)) || slug;
    title = title.replace(/\s*[—–-]\s*FishPoint\s*$/i, '').trim();
    const description = decode(
      pick(html, /<meta\s+name="description"\s+content="([\s\S]*?)"/i)
    );
    items.push({
      slug,
      url: `${SITE}/aktualnosci/${slug}.html`,
      title,
      description,
      mtime: statSync(path).mtimeMs,
      query: searchQueryFromTitle(title),
      note: description,
    });
  }
  // Od najświeższego (po dacie modyfikacji pliku).
  items.sort((a, b) => b.mtime - a.mtime);
  return items.slice(0, limit);
}
