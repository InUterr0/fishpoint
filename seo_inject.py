#!/usr/bin/env python3
"""Wstrzykuje meta SEO (canonical, OpenGraph, Twitter, JSON-LD) do wszystkich
stron HTML oraz generuje sitemap.xml i robots.txt.

Idempotentny: blok SEO jest oznaczony znacznikami i przy ponownym uruchomieniu
zostaje podmieniony, a nie zdublowany. Wystarczy zmienić BASE po kupnie domeny
i uruchomić ponownie: python3 seo_inject.py
"""
import os, re, html, json, datetime, subprocess, functools

BASE = "https://fish-point.pl"          # <-- PODMIEŃ po kupnie domeny i uruchom ponownie
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
}

title_re = re.compile(r"<title>(.*?)</title>", re.S)
desc_re = re.compile(r'<meta\s+name="description"\s+content="(.*?)"', re.S)
img_re = re.compile(r'<img[^>]+src="([^"]+)"', re.S)
block_re = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n", re.S)
tag_re = re.compile(r"<[^>]+>")


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
    # usuń poprzedni blok, by działać idempotentnie
    src = block_re.sub("", src)

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
    img_url = BASE + img_path

    parts = rel.split("/")
    section = parts[0] if len(parts) > 1 else None
    is_home = rel == "index.html"
    is_section_index = len(parts) == 2 and parts[1] == "index.html"

    pubdate, mtime = git_dates(path)

    # --- OpenGraph + Twitter ---
    og_type = "website" if (is_home or is_section_index) else "article"
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
    if og_type == "article":
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
                return new_src, url, mtime, is_home or is_section_index, title_txt, desc_txt
            posting = {
                "@context": "https://schema.org",
                "@type": "BlogPosting",
                "headline": title_txt.split(" — ")[0].split(" - ")[0],
                "description": desc_txt,
                "url": url,
                "mainEntityOfPage": url,
                "image": img_url,
                "inLanguage": "pl-PL",
                "datePublished": pubdate,
                "dateModified": mtime,
                "author": AUTHOR,
                "publisher": {
                    "@type": "Organization", "name": SITE_NAME,
                    "logo": {"@type": "ImageObject", "url": BASE + LOGO, "width": 512, "height": 512},
                },
            }
            # Powiązanie z encją gatunku ryby (Wikipedia + Wikidata) na stronach atlasu
            slug = os.path.splitext(parts[-1])[0]
            fish = FISH_ENTITIES.get(slug) if section in ("ryby", "rodzaje-ryb") or "rodzaje-ryb" in rel else None
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
    return new_src, url, mtime, is_home or is_section_index, title_txt, desc_txt


def main():
    pages = []
    for dirpath, _, files in os.walk(ROOT):
        if "/.git" in dirpath:
            continue
        for fn in files:
            if fn.endswith(".html") and fn != "404.html":
                pages.append(os.path.join(dirpath, fn))
    pages.sort()

    urls = []
    changed = 0
    for p in pages:
        res = build(p)
        if not res:
            print("POMINIĘTO (brak title/desc):", p)
            continue
        new_src, url, mtime, is_index, title_txt, desc_txt = res
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_src)
        section = rel_url(p).strip("/").split("/")[0] if rel_url(p) != "/" else ""
        urls.append((url, mtime, is_index, rel_url(p), title_txt, desc_txt, section))
        changed += 1

    # sitemap.xml
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemap s.org/schemas/sitemap/0.9">'.replace("sitemap s", "sitemaps")]
    for url, mtime, is_index, rp, _title, _desc, _sec in sorted(urls):
        prio = "1.0" if rp == "/" else ("0.8" if is_index else "0.6")
        freq = "weekly" if is_index or rp == "/" else "monthly"
        sm.append("  <url>")
        sm.append(f"    <loc>{url}</loc>")
        sm.append(f"    <lastmod>{mtime}</lastmod>")
        sm.append(f"    <changefreq>{freq}</changefreq>")
        sm.append(f"    <priority>{prio}</priority>")
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
    robots = "User-agent: *\nAllow: /\n\n"
    for bot in ai_bots:
        robots += f"User-agent: {bot}\nAllow: /\n\n"
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
    for url, mtime, is_index, rp, title, desc, sec in sorted(urls):
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

    print(f"Zaktualizowano stron: {changed}")
    print(f"sitemap.xml: {len(urls)} URL-i")
    print("robots.txt: ok")
    print(f"llms.txt: {sum(len(v) for v in by_sec.values())} wpisów")


if __name__ == "__main__":
    main()
