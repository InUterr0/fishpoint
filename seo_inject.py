#!/usr/bin/env python3
"""Wstrzykuje meta SEO (canonical, OpenGraph, Twitter, JSON-LD) do wszystkich
stron HTML oraz generuje sitemap.xml i robots.txt.

Idempotentny: blok SEO jest oznaczony znacznikami i przy ponownym uruchomieniu
zostaje podmieniony, a nie zdublowany. Wystarczy zmienić BASE po kupnie domeny
i uruchomić ponownie: python3 seo_inject.py
"""
import os, re, html, json, datetime, subprocess, functools

BASE = "https://fish-point.pl"          # <-- PODMIEŃ po kupnie domeny i uruchom ponownie
GA_ID = "G-33TKR9MEB7"                   # <-- Google Analytics 4 Measurement ID (G-XXXXXXX); puste = wyłączone
# Komentarze giscus (GitHub Discussions) — na wpisach blogowych (aktualnosci).
# Puste GISCUS_REPO = wyłączone. Wymaga zainstalowania aplikacji giscus na repo.
GISCUS_REPO = "InUterr0/fishpoint"
GISCUS_REPO_ID = "R_kgDOS3rnng"
GISCUS_CATEGORY = "Announcements"
GISCUS_CATEGORY_ID = "DIC_kwDOS3rnns4DA1tx"
# Newsletter — wklej TU pełny kod osadzenia formularza MailerLite (HTML/script).
# Puste = sekcja newslettera się nie pojawia. Po wklejeniu pojawi się na wpisach blogowych.
NEWSLETTER_EMBED = ""
SITE_NAME = "FishPoint"
AUTHOR_NAME = "Maciej Baniewicz"
DEFAULT_IMG = "/assets/img/tematy/wedki.jpg"
LOGO = "/assets/img/logo.png"          # kwadratowe logo marki (dla schema.org)

AUTHOR = {
    "@type": "Person",
    "name": AUTHOR_NAME,
    "url": BASE + "/o-autorze.html",
    "sameAs": ["https://www.facebook.com/profile.php?id=61591546555168"],
}

# Encje gatunków ryb -> Wikipedia + Wikidata (weryfikowane przez pl.wikipedia API).
# Pozwala Google i modelom AI jednoznacznie powiązać podstrony atlasu ze znanymi
# encjami (entity grounding = większa szansa na cytowanie w odpowiedziach AI).
FISH_ENTITIES = {
    "szczupak": {"name": "Szczupak pospolity", "sameAs": ["https://pl.wikipedia.org/wiki/Szczupak_pospolity", "https://www.wikidata.org/wiki/Q165278"]},
    "sandacz": {"name": "Sandacz pospolity", "sameAs": ["https://pl.wikipedia.org/wiki/Sandacz_pospolity", "https://www.wikidata.org/wiki/Q146641"]},
    "okon": {"name": "Okoń pospolity", "sameAs": ["https://pl.wikipedia.org/wiki/Okoń_pospolity", "https://www.wikidata.org/wiki/Q166812"]},
    "sum": {"name": "Sum pospolity", "sameAs": ["https://pl.wikipedia.org/wiki/Sum_pospolity", "https://www.wikidata.org/wiki/Q159323"]},
    "bolen": {"name": "Boleń", "sameAs": ["https://pl.wikipedia.org/wiki/Boleń", "https://www.wikidata.org/wiki/Q16277070"]},
    "wegorz": {"name": "Węgorz europejski", "sameAs": ["https://pl.wikipedia.org/wiki/Węgorz_europejski", "https://www.wikidata.org/wiki/Q26387"]},
    "karp": {"name": "Karp", "sameAs": ["https://pl.wikipedia.org/wiki/Karp", "https://www.wikidata.org/wiki/Q81110"]},
    "lin": {"name": "Lin (ryba)", "sameAs": ["https://pl.wikipedia.org/wiki/Lin_(ryba)", "https://www.wikidata.org/wiki/Q76280"]},
    "leszcz": {"name": "Leszcz", "sameAs": ["https://pl.wikipedia.org/wiki/Leszcz", "https://www.wikidata.org/wiki/Q144534"]},
    "jaz": {"name": "Jaź", "sameAs": ["https://pl.wikipedia.org/wiki/Jaź", "https://www.wikidata.org/wiki/Q144497"]},
    "pstrag": {"name": "Pstrąg potokowy", "sameAs": ["https://pl.wikipedia.org/wiki/Pstrąg_potokowy", "https://www.wikidata.org/wiki/Q1671485"]},
    "mietus": {"name": "Miętus pospolity", "sameAs": ["https://pl.wikipedia.org/wiki/Miętus_pospolity", "https://www.wikidata.org/wiki/Q144700"]},
    "lipien": {"name": "Lipień pospolity", "sameAs": ["https://pl.wikipedia.org/wiki/Lipień_pospolity", "https://www.wikidata.org/wiki/Q627960"]},
    "ploc": {"name": "Płoć", "sameAs": ["https://pl.wikipedia.org/wiki/Płoć", "https://www.wikidata.org/wiki/Q182976"]},
    "klen": {"name": "Kleń", "sameAs": ["https://pl.wikipedia.org/wiki/Kleń", "https://www.wikidata.org/wiki/Q26821893"]},
    "amur": {"name": "Amur biały", "sameAs": ["https://pl.wikipedia.org/wiki/Amur_biały", "https://www.wikidata.org/wiki/Q76098"]},
    "karas": {"name": "Karaś pospolity", "sameAs": ["https://pl.wikipedia.org/wiki/Karaś_pospolity", "https://www.wikidata.org/wiki/Q194031"]},
    "troc-losos": {"name": "Troć wędrowna", "sameAs": ["https://pl.wikipedia.org/wiki/Troć_wędrowna", "https://www.wikidata.org/wiki/Q1095355"]},
    "sielawa": {"name": "Sielawa", "sameAs": ["https://pl.wikipedia.org/wiki/Sielawa_europejska", "https://www.wikidata.org/wiki/Q754061"]},
    "sieja": {"name": "Sieja", "sameAs": ["https://pl.wikipedia.org/wiki/Sieja", "https://www.wikidata.org/wiki/Q9336436"]},
    "brzana": {"name": "Brzana", "sameAs": ["https://pl.wikipedia.org/wiki/Brzana", "https://www.wikidata.org/wiki/Q16290471"]},
    "certa": {"name": "Certa", "sameAs": ["https://pl.wikipedia.org/wiki/Certa", "https://www.wikidata.org/wiki/Q247370"]},
    "swinka": {"name": "Świnka pospolita", "sameAs": ["https://pl.wikipedia.org/wiki/Świnka_pospolita", "https://www.wikidata.org/wiki/Q654583"]},
    "wzdrega": {"name": "Wzdręga", "sameAs": ["https://pl.wikipedia.org/wiki/Wzdręga", "https://www.wikidata.org/wiki/Q200594"]},
    "ukleja": {"name": "Ukleja", "sameAs": ["https://pl.wikipedia.org/wiki/Ukleja", "https://www.wikidata.org/wiki/Q9364547"]},
    "jesiotr": {"name": "Jesiotr ostronosy", "sameAs": ["https://pl.wikipedia.org/wiki/Jesiotr_ostronosy", "https://www.wikidata.org/wiki/Q756969"]},
    "dorsz": {"name": "Dorsz atlantycki", "sameAs": ["https://pl.wikipedia.org/wiki/Dorsz_atlantycki", "https://www.wikidata.org/wiki/Q199788"]},
    "sledz": {"name": "Śledź atlantycki", "sameAs": ["https://pl.wikipedia.org/wiki/Śledź_oceaniczny", "https://www.wikidata.org/wiki/Q2396858"]},
    "belona": {"name": "Belona", "sameAs": ["https://pl.wikipedia.org/wiki/Belona_(ryba)", "https://www.wikidata.org/wiki/Q643373"]},
    "fladra": {"name": "Flądra (stornia)", "sameAs": ["https://pl.wikipedia.org/wiki/Stornia", "https://www.wikidata.org/wiki/Q214034"]},
}

ROOT = os.path.dirname(os.path.abspath(__file__))
BEGIN = "  <!-- seo:meta begin (auto) -->"
END = "  <!-- seo:meta end (auto) -->"

SECTIONS = {
    "ryby": "Atlas ryb",
    "poradniki": "Poradniki",
    "kuchnia": "Kuchnia",
    "aktualnosci": "Blog",
    "sprzet": "Sprzęt",
    "techniki": "Techniki",
    "pierwsze-kroki": "Pierwsze kroki",
    "narzedzia": "Narzędzia",
}

title_re = re.compile(r"<title>(.*?)</title>", re.S)
desc_re = re.compile(r'<meta\s+name="description"\s+content="(.*?)"', re.S)
img_re = re.compile(r'<img[^>]+src="([^"]+)"', re.S)
block_re = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n", re.S)
tag_re = re.compile(r"<[^>]+>")

# Idempotentne wstrzyknięcia w BODY (usuwane i odtwarzane przy każdym uruchomieniu)
BYLINE_BEGIN, BYLINE_END = "<!--byline:auto-->", "<!--/byline:auto-->"
byline_re = re.compile(re.escape(BYLINE_BEGIN) + r".*?" + re.escape(BYLINE_END), re.S)
MONTHS_PL = ["", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
             "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]


def fmt_date_pl(iso):
    """'2026-06-11' -> '11 czerwca 2026'."""
    try:
        y, m, d = iso.split("-")
        return f"{int(d)} {MONTHS_PL[int(m)]} {y}"
    except Exception:
        return iso


TOC_BEGIN, TOC_END = "<!--toc:auto-->", "<!--/toc:auto-->"
toc_re = re.compile(re.escape(TOC_BEGIN) + r".*?" + re.escape(TOC_END), re.S)

TLDR_BEGIN, TLDR_END = "<!--tldr:auto-->", "<!--/tldr:auto-->"
tldr_re = re.compile(re.escape(TLDR_BEGIN) + r".*?" + re.escape(TLDR_END), re.S)
RELATED_BEGIN, RELATED_END = "<!--related:auto-->", "<!--/related:auto-->"
related_re = re.compile(re.escape(RELATED_BEGIN) + r".*?" + re.escape(RELATED_END), re.S)
NEWSLETTER_BEGIN, NEWSLETTER_END = "<!--newsletter:auto-->", "<!--/newsletter:auto-->"
newsletter_re = re.compile(re.escape(NEWSLETTER_BEGIN) + r".*?" + re.escape(NEWSLETTER_END), re.S)
GISCUS_BEGIN, GISCUS_END = "<!--giscus:auto-->", "<!--/giscus:auto-->"
giscus_re = re.compile(re.escape(GISCUS_BEGIN) + r".*?" + re.escape(GISCUS_END), re.S)

# Mapa sekcja -> [(url, krótki_tytuł)] budowana w main() przed pętlą (dla bloku
# „Powiązane artykuły"). Puste do czasu prescanu.
SECTION_PAGES = {}


def short_title(title_txt):
    return title_txt.split(" — ")[0].split(" - ")[0]


def article_text(src):
    """Czysty tekst artykułu (z <article class="article-card">) — do wordCount
    i llms-full.txt. Usuwa skrypty, style, TOC i znaczniki."""
    m = re.search(r'<article class="article-card">(.*?)</article>', src, re.S)
    chunk = m.group(1) if m else src
    chunk = re.sub(r"<script.*?</script>", " ", chunk, flags=re.S)
    chunk = re.sub(r"<style.*?</style>", " ", chunk, flags=re.S)
    chunk = toc_re.sub(" ", chunk)
    chunk = tldr_re.sub(" ", chunk)
    chunk = related_re.sub(" ", chunk)
    chunk = newsletter_re.sub(" ", chunk)
    chunk = giscus_re.sub(" ", chunk)
    return re.sub(r"\s+", " ", _clean(chunk)).strip()


def build_related(section, url):
    """Do 4 innych artykułów z tej samej sekcji (deterministycznie)."""
    pool = [(u, t) for (u, t) in SECTION_PAGES.get(section, []) if u != url]
    pool.sort(key=lambda x: x[1].lower())
    return pool[:4]


def extract_howto(src):
    """Zwraca listę kroków, jeśli strona ma wyraźną listę „krok po kroku"
    (uporządkowaną <ol> z min. 3 <li> pod nagłówkiem zawierającym 'krok').
    Inaczej []. Pomija przepisy (obsługiwane osobno jako Recipe)."""
    for hm in re.finditer(r"<h[23][^>]*>[^<]*krok[^<]*</h[23]>", src, re.I):
        rest = src[hm.end():]
        nxt = re.search(r"<h[23][\s>]", rest)
        chunk = rest[: nxt.start()] if nxt else rest
        om = re.search(r"<ol[^>]*>(.*?)</ol>", chunk, re.S)
        if not om:
            continue
        steps = [_clean(li) for li in re.findall(r"<li>(.*?)</li>", om.group(1), re.S)]
        steps = [s for s in steps if s]
        if len(steps) >= 3:
            return steps
    return []


def extract_glossary(src):
    """Dla słownika: pary (termin, definicja) z <h3>Termin</h3><p>...</p>."""
    pairs = []
    for m in re.finditer(r"<h3[^>]*>(.*?)</h3>\s*<p>(.*?)</p>", src, re.S):
        term, definition = _clean(m.group(1)), _clean(m.group(2))
        if term and definition and len(term) < 60:
            pairs.append((term, definition))
    return pairs
_PL = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def slugify(text):
    s = _clean(text).translate(_PL).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "sekcja"


def add_toc_and_anchors(src):
    """Na stronach z <article class="article-card"> nadaje nagłówkom h2 kotwice
    (id ze slug-a) i wstawia spis treści na początku artykułu. Idempotentne.
    Zwraca (nowy_src, liczba_pozycji_toc)."""
    m = re.search(r'(<article class="article-card">)(.*?)(</article>)', src, re.S)
    if not m:
        return src, 0
    inner = m.group(2)
    seen, toc = {}, []

    def repl(hm):
        attrs, text = hm.group(1), hm.group(2)
        if re.search(r'\bid=', attrs):
            hid = re.search(r'id="([^"]+)"', attrs)
            hid = hid.group(1) if hid else slugify(text)
        else:
            base = slugify(text)
            hid = base
            i = 2
            while hid in seen:
                hid = f"{base}-{i}"; i += 1
            attrs = attrs + f' id="{hid}"'
        seen[hid] = True
        toc.append((hid, _clean(text)))
        return f"<h2{attrs}>{text}</h2>"

    new_inner = re.sub(r"<h2([^>]*)>(.*?)</h2>", repl, inner, flags=re.S)
    if len(toc) < 3:
        return src, 0
    items = "".join(f'<li><a href="#{hid}">{html.escape(t)}</a></li>' for hid, t in toc)
    toc_html = (f'{TOC_BEGIN}<nav class="toc" aria-label="Spis treści">'
                f'<p class="toc-title">Spis treści</p><ol>{items}</ol></nav>{TOC_END}')
    new_inner = toc_html + new_inner
    return src[:m.start()] + m.group(1) + new_inner + m.group(3) + src[m.end():], len(toc)


def _clean(s):
    return html.unescape(tag_re.sub("", s)).strip()


def _list_after(src, heading_pat):
    """Zwraca teksty <li> z pierwszej NIEPUSTEJ listy następującej po nagłówku
    pasującym do heading_pat (do najbliższego kolejnego <h2>/<h3>).
    Iteruje po wszystkich pasujących nagłówkach — pomija te, pod którymi
    znajduje się akapit bez listy."""
    for hm in re.finditer(heading_pat, src, re.I):
        rest = src[hm.end():]
        nxt = re.search(r"<h[23][\s>]", rest)
        chunk = rest[: nxt.start()] if nxt else rest
        items = [_clean(li) for li in re.findall(r"<li>(.*?)</li>", chunk, re.S)]
        items = [i for i in items if i]
        if items:
            return items
    return []


def extract_faq(src):
    """Zwraca listę (pytanie, odpowiedź) z widocznej sekcji FAQ na stronie.
    Kotwiczy się na nagłówku zawierającym 'FAQ' i bierze pary
    <h3>...?</h3><p>...</p>. Pomija nagłówki nie będące pytaniami
    (np. 'Źródła i weryfikacja'). Zwraca [] gdy brak FAQ."""
    fm = re.search(r"<h2[^>]*>[^<]*FAQ", src, re.I)
    if not fm:
        return []
    region = src[fm.end():]
    pairs = []
    for m in re.finditer(r"<h3[^>]*>\s*([^<]*\?)\s*</h3>\s*<p>(.*?)</p>", region, re.S):
        q = _clean(m.group(1))
        a = _clean(m.group(2))
        if q and a:
            pairs.append((q, a))
    return pairs


def extract_recipe(src):
    """Zwraca (skladniki, kroki) jeśli strona wygląda na przepis, inaczej None."""
    ingredients = _list_after(src, r"<h[23][^>]*>\s*Składnik")
    steps = _list_after(src, r"<h[23][^>]*>[^<]*(?:krok po kroku|Przygotowanie)")
    if ingredients and steps:
        return ingredients, steps
    return None


def extract_listitems(src, url):
    """Dla strony-indeksu sekcji zwraca [(nazwa, absolutny_url)] z kart
    linkujących do podstron tej sekcji. Nazwa = tekst <h3> w karcie."""
    base_dir = url.rsplit("/", 1)[0] + "/"
    items, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="([^"]+\.html)"[^>]*>(.*?)</a>', src, re.S):
        href, inner = m.group(1), m.group(2)
        if href.startswith(("http", "..", "/")) or "index.html" in href:
            continue
        # 1) nagłówek wewnątrz karty-linku (kafelki kategorii)
        hm = re.search(r"<h[234][^>]*>(.*?)</h[234]>", inner, re.S)
        name = _clean(hm.group(1)) if hm else ""
        # 2) fallback: najbliższy nagłówek PRZED linkiem (karty blog/artykuł,
        #    gdzie link to samo "Czytaj więcej →")
        if not name:
            before = src[:m.start()]
            hs = re.findall(r"<h[234][^>]*>(.*?)</h[234]>", before, re.S)
            if hs:
                name = _clean(hs[-1])
        if not name:
            continue
        full = base_dir + href
        if full in seen:
            continue
        seen.add(full)
        items.append((name, full))
    return items


img_tag_re = re.compile(r"<img\b[^>]*>", re.I)
attr_src_re = re.compile(r'src="([^"]+)"')
attr_alt_re = re.compile(r'alt="([^"]*)"')


def collect_images(src, page_dir):
    """Zwraca [(absolutny_url_obrazu, alt)] dla wszystkich <img> na stronie
    wskazujących na zasoby serwisu. Dedup po URL, zachowuje kolejność.
    Zasila image sitemap (indeksacja w Grafice Google) i GEO."""
    out, seen = [], set()
    for tag in img_tag_re.findall(src):
        m = attr_src_re.search(tag)
        if not m:
            continue
        s = m.group(1)
        if s.startswith("data:"):
            continue
        img_path = resolve_img(s, page_dir)
        u = img_path if img_path.startswith("http") else BASE + img_path
        if u in seen:
            continue
        seen.add(u)
        alt_m = attr_alt_re.search(tag)
        alt = html.unescape(alt_m.group(1).strip()) if alt_m else ""
        out.append((u, alt))
    return out


def rel_url(path):
    """Ścieżka pliku -> URL względny od korenia serwisu (zachowuje .html)."""
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel


def resolve_img(src, page_dir):
    """Zamienia src obrazka (relatywny do strony) na ścieżkę od korenia serwisu."""
    if src.startswith("http"):
        return src
    abs_fs = os.path.normpath(os.path.join(page_dir, src))
    rel = os.path.relpath(abs_fs, ROOT).replace(os.sep, "/")
    return "/" + rel


def _git(args):
    try:
        out = subprocess.run(["git", "-C", ROOT] + args,
                             capture_output=True, text=True, timeout=15)
        return out.stdout.strip()
    except Exception:
        return ""


@functools.lru_cache(maxsize=None)
def git_dates(path):
    """(datePublished, dateModified) z historii git: data dodania pliku i
    data ostatniej zmiany. Odporne na to, że przebudowa zmienia mtime pliku.
    Fallback do mtime, gdy plik nie jest jeszcze w gicie."""
    rel = os.path.relpath(path, ROOT)
    added = _git(["log", "--diff-filter=A", "--follow", "--format=%as", "--", rel])
    modified = _git(["log", "-1", "--format=%as", "--", rel])
    added = added.splitlines()[-1] if added else ""
    if not added or not modified:
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")
        return mt, mt
    return added, modified


def jsonld(obj):
    return '  <script type="application/ld+json">\n' + json.dumps(
        obj, ensure_ascii=False, indent=2
    ) + "\n  </script>"


def build(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    # usuń poprzednie wstrzyknięcia, by działać idempotentnie
    src = block_re.sub("", src)
    src = byline_re.sub("", src)
    src = toc_re.sub("", src)
    src = tldr_re.sub("", src)
    src = related_re.sub("", src)
    src = newsletter_re.sub("", src)
    src = giscus_re.sub("", src)

    tm = title_re.search(src)
    dm = desc_re.search(src)
    if not tm or not dm:
        return None
    title_raw = tm.group(1).strip()
    desc_raw = dm.group(1).strip()
    title_txt = html.unescape(title_raw)
    desc_txt = html.unescape(desc_raw)

    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    url = BASE + rel_url(path)

    # obrazek OG: pierwszy <img> w treści, inaczej domyślny
    page_dir = os.path.dirname(path)
    im = img_re.search(src)
    img_path = resolve_img(im.group(1), page_dir) if im else DEFAULT_IMG
    # Strony narzędzi budują <img> w JS (brak statycznego) — nadaj sensowny OG
    TOOL_IMG = {
        "narzedzia/okresy-ochronne.html": "/assets/img/tematy/wedki.jpg",
        "narzedzia/prognoza-bran.html": "/assets/img/tematy/kalendarz.jpg",
        "narzedzia/kalendarz-bran.html": "/assets/img/tematy/kalendarz.jpg",
        "narzedzia/dobor-sprzetu.html": "/assets/img/tematy/wedki.jpg",
        "narzedzia/rozpoznaj-rybe.html": "/assets/img/ryby/okon.jpg",
        "narzedzia/index.html": "/assets/img/tematy/wedki.jpg",
    }
    rel_now = os.path.relpath(path, ROOT).replace(os.sep, "/")
    if rel_now in TOOL_IMG:
        img_path = TOOL_IMG[rel_now]
    # Jawny obraz OG per-strona: <!--og-image:/assets/img/...-->. Przydatne dla
    # wpisów bez zdjęcia w treści (blog), by każdy miał własny podgląd na FB/X.
    m_og = re.search(r"<!--\s*og-image:\s*([^\s>]+?)\s*-->", src)
    if m_og:
        img_path = m_og.group(1)
    img_url = BASE + img_path
    page_images = collect_images(src, page_dir)

    parts = rel.split("/")
    section = parts[0] if len(parts) > 1 else None
    is_home = rel == "index.html"
    is_section_index = len(parts) == 2 and parts[1] == "index.html"

    pubdate, mtime = git_dates(path)

    # --- OpenGraph + Twitter ---
    og_type = "website" if (is_home or is_section_index) else "article"

    # --- Widoczny podpis autora + daty (E-E-A-T, świeżość) na artykułach ---
    # Wstrzykiwany po pierwszym </h1>; pomijamy strony autora, słownik i przepisy.
    if og_type == "article" and rel not in ("o-autorze.html",):
        byline = (
            f'{BYLINE_BEGIN}<p class="article-meta">'
            f'Autor: <a href="{BASE}/o-autorze.html" rel="author">{AUTHOR_NAME}</a>'
            f' · <time datetime="{pubdate}">Opublikowano {fmt_date_pl(pubdate)}</time>'
            f' · <time datetime="{mtime}">aktualizacja {fmt_date_pl(mtime)}</time>'
            f'</p>{BYLINE_END}'
        )
        src, n = re.subn(r"(</h1>)", r"\1" + byline, src, count=1)
        src, _toc_n = add_toc_and_anchors(src)
        # „W skrócie" (TL;DR) — z opisu meta; łatwe do wyciągnięcia przez AI/Google
        tldr = (f'{TLDR_BEGIN}<aside class="tldr" aria-label="W skrócie">'
                f'<p class="tldr-label">W skrócie</p><p>{html.escape(desc_txt)}</p>'
                f'</aside>{TLDR_END}')
        src = re.sub(r'(<article class="article-card">)', r"\1" + tldr, src, count=1)
        # „Powiązane artykuły" — linki wewnętrzne z tej samej sekcji
        if section:
            rel_items = build_related(section, url)
            if rel_items:
                links = "".join(
                    f'<a href="{u}">{html.escape(t)}</a>' for u, t in rel_items)
                related = (f'{RELATED_BEGIN}<section class="related" aria-label="Powiązane artykuły">'
                           f'<h2>Powiązane artykuły</h2><div class="related-grid">{links}</div>'
                           f'</section>{RELATED_END}')
                src = re.sub(r"(</article>)", related + r"\1", src, count=1)
        # Newsletter (MailerLite) — na wpisach blogowych, gdy ustawiono embed
        if section == "aktualnosci" and NEWSLETTER_EMBED:
            nl = (f'{NEWSLETTER_BEGIN}<section class="newsletter" aria-label="Newsletter">'
                  f'<h2>Bierze? Bądź pierwszy nad wodą</h2>'
                  f'<p>Zapisz się na newsletter FishPoint — najlepsze brania weekendu, nowe poradniki '
                  f'i sezonowe wskazówki prosto na e-mail. Bez spamu, wypiszesz się jednym kliknięciem.</p>'
                  f'{NEWSLETTER_EMBED}</section>{NEWSLETTER_END}')
            src = re.sub(r"(</article>)", nl + r"\1", src, count=1)
        # Komentarze giscus — na wpisach blogowych (aktualnosci)
        if section == "aktualnosci" and GISCUS_REPO:
            giscus = (f'{GISCUS_BEGIN}<section class="comments" aria-label="Komentarze"><h2>Komentarze</h2>'
                      f'<script src="https://giscus.app/client.js" data-repo="{GISCUS_REPO}" '
                      f'data-repo-id="{GISCUS_REPO_ID}" data-category="{GISCUS_CATEGORY}" '
                      f'data-category-id="{GISCUS_CATEGORY_ID}" data-mapping="pathname" data-strict="1" '
                      f'data-reactions-enabled="1" data-emit-metadata="0" data-input-position="top" '
                      f'data-theme="light" data-lang="pl" data-loading="lazy" crossorigin="anonymous" async>'
                      f'</script></section>{GISCUS_END}')
            src = re.sub(r"(</article>)", giscus + r"\1", src, count=1)
    head = [
        BEGIN,
        f'  <link rel="canonical" href="{url}" />',
        '  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />',
        f'  <meta name="author" content="{AUTHOR_NAME}" />',
        '  <meta name="theme-color" content="#0e5e54" />',
        '  <link rel="icon" type="image/svg+xml" href="/assets/img/logo.svg" />',
        '  <link rel="icon" type="image/png" sizes="512x512" href="/assets/img/logo.png" />',
        '  <link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png" />',
        '  <link rel="manifest" href="/site.webmanifest" />',
        '  <link rel="alternate" type="application/rss+xml" title="FishPoint — aktualności" href="/feed.xml" />',
        f'  <meta property="og:site_name" content="{SITE_NAME}" />',
        '  <meta property="og:locale" content="pl_PL" />',
        f'  <meta property="og:type" content="{og_type}" />',
        f'  <meta property="og:title" content="{title_raw}" />',
        f'  <meta property="og:description" content="{desc_raw}" />',
        f'  <meta property="og:url" content="{url}" />',
        f'  <meta property="og:image" content="{img_url}" />',
        '  <meta name="twitter:card" content="summary_large_image" />',
        f'  <meta name="twitter:title" content="{title_raw}" />',
        f'  <meta name="twitter:description" content="{desc_raw}" />',
        f'  <meta name="twitter:image" content="{img_url}" />',
    ]
    # Google Analytics 4 (gtag) — na wszystkich stronach, gdy ustawiono GA_ID.
    if GA_ID:
        head.append(f'  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>')
        head.append(
            '  <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
            f"gtag('js',new Date());gtag('config','{GA_ID}');</script>"
        )
    if og_type == "article":
        if im:
            head.append(f'  <link rel="preload" as="image" href="{img_path}" fetchpriority="high" />')
        head.append(f'  <meta property="article:published_time" content="{pubdate}" />')
        head.append(f'  <meta property="article:modified_time" content="{mtime}" />')
        head.append('  <meta property="article:publisher" content="' + BASE + '/" />')

    # --- JSON-LD ---
    if is_home:
        head.append(jsonld({
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": SITE_NAME,
            "url": BASE + "/",
            "logo": {"@type": "ImageObject", "url": BASE + LOGO, "width": 512, "height": 512},
            "image": img_url,
            "email": "kerlinbygg@gmail.com",
            "founder": AUTHOR,
            "author": AUTHOR,
            "sameAs": [
                "https://www.facebook.com/profile.php?id=61591546555168",
            ],
            "description": desc_txt,
            "knowsAbout": [
                "wędkarstwo", "sprzęt wędkarski", "atlas ryb słodkowodnych",
                "techniki wędkarskie", "przynęty", "łowiska", "kuchnia rybna",
            ],
        }))
        head.append(jsonld({
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": SITE_NAME,
            "url": BASE + "/",
            "inLanguage": "pl-PL",
            "potentialAction": {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": BASE + "/szukaj.html?q={search_term_string}",
                },
                "query-input": "required name=search_term_string",
            },
        }))
    else:
        # breadcrumb
        crumbs = [{"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": BASE + "/"}]
        pos = 2
        if section:
            crumbs.append({
                "@type": "ListItem", "position": pos,
                "name": SECTIONS.get(section, section.capitalize()),
                "item": BASE + "/" + section + "/",
            })
            pos += 1
        if not is_section_index:
            crumbs.append({
                "@type": "ListItem", "position": pos,
                "name": title_txt.split(" — ")[0].split(" - ")[0],
                "item": url,
            })
        head.append(jsonld({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": crumbs,
        }))

        if rel == "o-autorze.html":
            head.append(jsonld({
                "@context": "https://schema.org",
                "@type": "ProfilePage",
                "name": title_txt,
                "description": desc_txt,
                "url": url,
                "inLanguage": "pl-PL",
                "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": BASE + "/"},
                "mainEntity": {
                    "@type": "Person",
                    "name": AUTHOR_NAME,
                    "url": url,
                    "image": BASE + "/assets/img/maciej-baniewicz-kwadrat.jpg",
                    "sameAs": ["https://www.facebook.com/profile.php?id=61591546555168"],
                    "email": "kerlinbygg@gmail.com",
                    "jobTitle": "Autor i twórca serwisu FishPoint",
                    "knowsAbout": [
                        "wędkarstwo", "sprzęt wędkarski", "atlas ryb słodkowodnych",
                        "techniki wędkarskie", "przynęty", "łowiska", "kuchnia rybna",
                    ],
                    "worksFor": {"@type": "Organization", "name": SITE_NAME, "url": BASE + "/"},
                },
            }))
        elif is_section_index:
            head.append(jsonld({
                "@context": "https://schema.org",
                "@type": "CollectionPage",
                "name": title_txt,
                "description": desc_txt,
                "url": url,
                "inLanguage": "pl-PL",
                "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": BASE + "/"},
            }))
            li = extract_listitems(src, url)
            if li:
                head.append(jsonld({
                    "@context": "https://schema.org",
                    "@type": "ItemList",
                    "name": title_txt,
                    "itemListOrder": "https://schema.org/ItemListOrderAscending",
                    "numberOfItems": len(li),
                    "itemListElement": [
                        {"@type": "ListItem", "position": i + 1,
                         "name": name, "url": u}
                        for i, (name, u) in enumerate(li)
                    ],
                }))
        elif rel == "slownik.html":
            terms = extract_glossary(src)
            if terms:
                head.append(jsonld({
                    "@context": "https://schema.org",
                    "@type": "DefinedTermSet",
                    "name": short_title(title_txt),
                    "description": desc_txt,
                    "url": url,
                    "inLanguage": "pl-PL",
                    "hasDefinedTerm": [
                        {"@type": "DefinedTerm", "name": term, "description": definition,
                         "inDefinedTermSet": url}
                        for term, definition in terms
                    ],
                }))
        else:
            faq = extract_faq(src)
            if faq:
                head.append(jsonld({
                    "@context": "https://schema.org",
                    "@type": "FAQPage",
                    "mainEntity": [
                        {
                            "@type": "Question",
                            "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a},
                        }
                        for q, a in faq
                    ],
                }))
            recipe = extract_recipe(src) if section == "kuchnia" else None
            if recipe:
                ingredients, steps = recipe
                head.append(jsonld({
                    "@context": "https://schema.org",
                    "@type": "Recipe",
                    "name": title_txt.split(" — ")[0].split(" - ")[0],
                    "description": desc_txt,
                    "url": url,
                    "mainEntityOfPage": url,
                    "image": img_url,
                    "inLanguage": "pl-PL",
                    "datePublished": pubdate,
                    "dateModified": mtime,
                    "recipeCategory": "Danie główne",
                    "recipeCuisine": "Polska",
                    "keywords": "ryby, wędkarstwo, przepis rybny",
                    "author": AUTHOR,
                    "recipeIngredient": ingredients,
                    "recipeInstructions": [
                        {"@type": "HowToStep", "position": i + 1, "text": s}
                        for i, s in enumerate(steps)
                    ],
                }))
                head.append(END)
                block = "\n".join(head) + "\n"
                new_src = re.sub(r"\n?</head>", "\n" + block + "</head>", src, count=1)
                return new_src, url, mtime, is_home or is_section_index, title_txt, desc_txt, page_images
            slug = os.path.splitext(parts[-1])[0]
            fish = FISH_ENTITIES.get(slug) if section in ("ryby", "rodzaje-ryb") or "rodzaje-ryb" in rel else None
            # ImageObject reprezentatywny: podpis z alt pierwszego obrazu, autor
            # i atrybucja. Na stronach atlasu obraz jawnie "przedstawia" gatunek
            # (about -> encja Wikipedia/Wikidata) — mocny sygnał dla Grafiki
            # Google i modeli AI (obraz powiązany ze znaną encją).
            first_alt = page_images[0][1] if page_images else ""
            img_obj = {
                "@type": "ImageObject",
                "url": img_url,
                "contentUrl": img_url,
                "creditText": SITE_NAME,
                "creator": AUTHOR,
                "copyrightNotice": f"© {SITE_NAME}",
            }
            if first_alt:
                img_obj["caption"] = first_alt
            if fish:
                img_obj["about"] = {"@type": "Thing", "name": fish["name"], "sameAs": fish["sameAs"]}
            posting = {
                "@context": "https://schema.org",
                "@type": "BlogPosting",
                "headline": title_txt.split(" — ")[0].split(" - ")[0],
                "description": desc_txt,
                "url": url,
                "mainEntityOfPage": url,
                "image": img_obj,
                "inLanguage": "pl-PL",
                "datePublished": pubdate,
                "dateModified": mtime,
                "author": AUTHOR,
                "publisher": {
                    "@type": "Organization", "name": SITE_NAME,
                    "logo": {"@type": "ImageObject", "url": BASE + LOGO, "width": 512, "height": 512},
                },
            }
            # Wzbogacenie: wordCount, sekcja, szacowany czas czytania, słowa kluczowe
            wc = len(article_text(src).split())
            if wc > 50:
                posting["wordCount"] = wc
                posting["timeRequired"] = f"PT{max(1, round(wc / 200))}M"
            if section:
                posting["articleSection"] = SECTIONS.get(section, section.capitalize())
            kw = [short_title(title_txt)]
            if section:
                kw.append(SECTIONS.get(section, section.capitalize()))
            kw.append("wędkarstwo")
            posting["keywords"] = ", ".join(dict.fromkeys(kw))
            # HowTo (poza kuchnią — przepisy mają własny Recipe): wyraźna lista kroków
            if section != "kuchnia":
                steps = extract_howto(src)
                if steps:
                    head.append(jsonld({
                        "@context": "https://schema.org",
                        "@type": "HowTo",
                        "name": short_title(title_txt),
                        "description": desc_txt,
                        "inLanguage": "pl-PL",
                        "step": [
                            {"@type": "HowToStep", "position": i + 1, "text": s}
                            for i, s in enumerate(steps)
                        ],
                    }))
            # Powiązanie z encją gatunku ryby (Wikipedia + Wikidata) na stronach atlasu
            if fish:
                posting["about"] = {
                    "@type": "Thing",
                    "name": fish["name"],
                    "sameAs": fish["sameAs"],
                }
            head.append(jsonld(posting))

    head.append(END)
    block = "\n".join(head) + "\n"

    # wstaw przed </head>
    new_src = re.sub(r"\n?</head>", "\n" + block + "</head>", src, count=1)
    return new_src, url, mtime, is_home or is_section_index, title_txt, desc_txt, page_images


def main():
    pages = []
    for dirpath, _, files in os.walk(ROOT):
        if "/.git" in dirpath:
            continue
        for fn in files:
            if fn.endswith(".html") and fn != "404.html":
                pages.append(os.path.join(dirpath, fn))
    pages.sort()

    # Pre-scan: mapa sekcja -> [(url, tytuł)] dla bloku „Powiązane artykuły".
    SECTION_PAGES.clear()
    for p in pages:
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        parts = rel.split("/")
        if len(parts) < 2 or parts[-1] == "index.html" or parts[0] not in SECTIONS:
            continue
        with open(p, encoding="utf-8") as f:
            tm = title_re.search(f.read())
        if not tm:
            continue
        SECTION_PAGES.setdefault(parts[0], []).append(
            (BASE + rel_url(p), short_title(html.unescape(tm.group(1).strip()))))

    urls = []
    changed = 0
    for p in pages:
        res = build(p)
        if not res:
            print("POMINIĘTO (brak title/desc):", p)
            continue
        new_src, url, mtime, is_index, title_txt, desc_txt, page_images = res
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_src)
        section = rel_url(p).strip("/").split("/")[0] if rel_url(p) != "/" else ""
        urls.append((url, mtime, is_index, rel_url(p), title_txt, desc_txt, section, page_images))
        changed += 1

    # sitemap.xml (z rozszerzeniem Image — indeksacja w Grafice Google)
    def xesc(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
          ' xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    total_imgs = 0
    for url, mtime, is_index, rp, _title, _desc, _sec, imgs in sorted(urls, key=lambda t: t[0]):
        prio = "1.0" if rp == "/" else ("0.8" if is_index else "0.6")
        freq = "weekly" if is_index or rp == "/" else "monthly"
        sm.append("  <url>")
        sm.append(f"    <loc>{url}</loc>")
        sm.append(f"    <lastmod>{mtime}</lastmod>")
        sm.append(f"    <changefreq>{freq}</changefreq>")
        sm.append(f"    <priority>{prio}</priority>")
        for iu, alt in imgs:
            sm.append("    <image:image>")
            sm.append(f"      <image:loc>{xesc(iu)}</image:loc>")
            if alt:
                sm.append(f"      <image:title>{xesc(alt)}</image:title>")
            sm.append("    </image:image>")
            total_imgs += 1
        sm.append("  </url>")
    sm.append("</urlset>")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(sm) + "\n")

    # robots.txt
    # Jawnie wpuszczamy roboty AI (GEO) — chcemy być cytowani w odpowiedziach
    # ChatGPT, Claude, Perplexity, Gemini itd.
    ai_bots = [
        "GPTBot", "OAI-SearchBot", "ChatGPT-User",
        "ClaudeBot", "Claude-Web", "anthropic-ai",
        "PerplexityBot", "Perplexity-User",
        "Google-Extended", "Applebot-Extended",
        "CCBot", "Bytespider", "Amazonbot", "cohere-ai",
    ]
    # /obrazy/ to wewnętrzne zrzuty robocze — nie deployujemy ich (patrz
    # .dockerignore); Disallow to dodatkowe zabezpieczenie na wypadek indeksacji.
    robots = "User-agent: *\nAllow: /\nDisallow: /obrazy/\n\n"
    for bot in ai_bots:
        robots += f"User-agent: {bot}\nAllow: /\nDisallow: /obrazy/\n\n"
    robots += f"Sitemap: {BASE}/sitemap.xml\n"
    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots)

    # llms.txt — mapa treści dla modeli AI (GEO). Standard: https://llmstxt.org
    ll = [
        "# FishPoint",
        "",
        "> FishPoint to polski poradnik wędkarski: dobór sprzętu, atlas ryb "
        "słodkowodnych, techniki połowu, opisy łowisk, poradniki dla początkujących "
        "i przepisy kuchni rybnej. Treści są autorskie, po polsku (pl-PL).",
        "",
    ]
    by_sec = {}
    home = None
    for url, mtime, is_index, rp, title, desc, sec, _imgs in sorted(urls):
        if rp == "/":
            home = (url, title, desc)
            continue
        by_sec.setdefault(sec or "inne", []).append((url, title, desc, is_index))
    if home:
        ll.append(f"- [{home[1]}]({home[0]}): {home[2]}")
        ll.append("")
    for sec in sorted(by_sec):
        ll.append(f"## {SECTIONS.get(sec, sec.capitalize())}")
        ll.append("")
        for url, title, desc, is_index in by_sec[sec]:
            short = title.split(" — ")[0].split(" - ")[0]
            ll.append(f"- [{short}]({url}): {desc}")
        ll.append("")
    with open(os.path.join(ROOT, "llms.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(ll).rstrip() + "\n")

    # llms-full.txt — pełny zrzut treści dla modeli AI (opcjonalny standard llmstxt)
    full = ["# FishPoint — pełna treść",
            "",
            "> Kompletny, tekstowy zrzut treści serwisu FishPoint (polski poradnik "
            "wędkarski: sprzęt, atlas ryb, techniki, poradniki, kuchnia, narzędzia). "
            "Autor: " + AUTHOR_NAME + ". Język: pl-PL.",
            ""]
    full_n = 0
    for p in pages:
        with open(p, encoding="utf-8") as f:
            s = f.read()
        tm = title_re.search(s)
        if not tm:
            continue
        txt = article_text(s)
        if len(txt) < 120:
            continue
        full.append(f"## {short_title(html.unescape(tm.group(1).strip()))}")
        full.append(f"URL: {BASE + rel_url(p)}")
        full.append("")
        full.append(txt)
        full.append("")
        full_n += 1
    with open(os.path.join(ROOT, "llms-full.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(full).rstrip() + "\n")

    # feed.xml (RSS 2.0) — kanał bloga (aktualnosci)
    import email.utils

    def rfc822(d):
        try:
            return email.utils.format_datetime(
                datetime.datetime.strptime(d, "%Y-%m-%d"))
        except Exception:
            return d

    blog = [u for u in urls if u[6] == "aktualnosci" and not u[2]]
    blog.sort(key=lambda t: t[1], reverse=True)
    rss = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
           '  <channel>',
           f'    <title>FishPoint — aktualności wędkarskie</title>',
           f'    <link>{BASE}/aktualnosci/</link>',
           '    <description>Blog wędkarski FishPoint: poradniki, relacje znad wody, '
           'sezon i sprzęt.</description>',
           '    <language>pl-PL</language>',
           f'    <atom:link href="{BASE}/feed.xml" rel="self" type="application/rss+xml" />']
    if blog:
        rss.append(f'    <lastBuildDate>{rfc822(blog[0][1])}</lastBuildDate>')
    for url, mtime, _is_index, _rp, title, desc, _sec, _imgs in blog:
        rss += ['    <item>',
                f'      <title>{xesc(short_title(title))}</title>',
                f'      <link>{url}</link>',
                f'      <guid isPermaLink="true">{url}</guid>',
                f'      <pubDate>{rfc822(mtime)}</pubDate>',
                f'      <description>{xesc(desc)}</description>',
                '    </item>']
    rss += ['  </channel>', '</rss>']
    with open(os.path.join(ROOT, "feed.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(rss) + "\n")

    print(f"Zaktualizowano stron: {changed}")
    print(f"llms-full.txt: {full_n} stron; feed.xml: {len(blog)} wpisów")
    print(f"sitemap.xml: {len(urls)} URL-i, {total_imgs} obrazów")
    print("robots.txt: ok")
    print(f"llms.txt: {sum(len(v) for v in by_sec.values())} wpisów")


if __name__ == "__main__":
    main()
