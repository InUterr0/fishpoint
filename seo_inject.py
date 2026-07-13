#!/usr/bin/env python3
"""Wstrzykuje meta SEO (canonical, OpenGraph, Twitter, JSON-LD) do wszystkich
stron HTML oraz generuje sitemap.xml i robots.txt.

Idempotentny: blok SEO jest oznaczony znacznikami i przy ponownym uruchomieniu
zostaje podmieniony, a nie zdublowany. Wystarczy zmienić BASE po kupnie domeny
i uruchomić ponownie: python3 seo_inject.py
"""
import os, re, html, json, datetime, subprocess, functools, hashlib, sys

BASE = "https://fish-point.pl"          # <-- PODMIEŃ po kupnie domeny i uruchom ponownie
GA_ID = "G-33TKR9MEB7"                   # <-- Google Analytics 4 Measurement ID (G-XXXXXXX); puste = wyłączone
# Komentarze giscus (GitHub Discussions) — na wpisach blogowych (aktualnosci).
# Puste GISCUS_REPO = wyłączone. Wymaga zainstalowania aplikacji giscus na repo.
GISCUS_REPO = "kerlingruppen/fishpoint-comments"
GISCUS_REPO_ID = "R_kgDOTTiC_g"
GISCUS_CATEGORY = "Announcements"
GISCUS_CATEGORY_ID = "DIC_kwDOTTiC_s4DA1zO"
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
    "lowiska": "Łowiska",
    "forum": "Forum",
    "humor": "Humor",
}

# --- Wspólna nawigacja z rozwijanymi działami (dropdown), wstrzykiwana na KAŻDĄ
# stronę, żeby menu było identyczne wszędzie. (etykieta, href względny od korzenia,
# klucz sekcji dla dzieci menu lub None). Dzieci pobierane są z SECTION_PAGES. ---
NAV_TOP = [
    ("Pierwsze kroki", "pierwsze-kroki/", "pierwsze-kroki"),
    ("Sprzęt", "sprzet/", "sprzet"),
    ("Techniki", "techniki/", "techniki"),
    ("Atlas ryb", "ryby/", "ryby"),
    ("Poradniki", "poradniki/", "poradniki"),
    ("Narzędzia", "narzedzia/", "narzedzia"),
    ("Łowiska", "lowiska/", "lowiska"),
    ("Forum", "forum/", None),
    ("Blog", "aktualnosci/", "aktualnosci"),
    ("Zakupy", "zakupy.html", None),
    ("Więcej", "slownik.html", "__more__"),
]
NAV_CTA = ("Kontakt", "./#kontakt")
NAV_MORE = [
    ("humor/", "Humor wędkarski"),
    ("kuchnia/", "Kuchnia wędkarska"),
    ("zgodnie-z-zasadami.html", "Przepisy i dokumenty"),
    ("slownik.html", "Słownik pojęć"),
    ("szukaj.html", "Szukaj w serwisie"),
]
nav_re = re.compile(r'<header class="site-header">.*?</header>', re.S)

# Cache-busting CSS: wersja z hasha zawartości arkusza — po każdej zmianie CSS
# link zmienia się, więc przeglądarki pobierają nowy plik (koniec ze starym cache).
try:
    with open(os.path.join(ROOT, "css", "style.css"), "rb") as _f:
        CSS_VER = hashlib.md5(_f.read()).hexdigest()[:8]
except OSError:
    CSS_VER = "1"
css_ver_re = re.compile(r'css/style\.css(\?v=[0-9a-f]+)?"')
index_href_re = re.compile(r'href="([^"]*?)index\.html([?#][^"]*)?"', re.I)


def canonicalize_internal_hrefs(src):
    """Zamienia wewnętrzne odnośniki do index.html na adresy katalogowe."""
    def repl(match):
        prefix, suffix = match.group(1), match.group(2) or ""
        if prefix.startswith(("http://", "https://", "//")):
            if prefix.startswith(BASE + "/") or prefix == BASE:
                return f'href="{prefix}{suffix}"'
            return match.group(0)
        return f'href="{prefix or "./"}{suffix}"'

    return index_href_re.sub(repl, src)


def _nav_children(section, prefix):
    if section == "__more__":
        return [(prefix + href, title) for href, title in NAV_MORE]
    out = []
    for url, title in SECTION_PAGES.get(section, []):
        rel = url[len(BASE) + 1:] if url.startswith(BASE + "/") else url
        if rel == "" or rel.endswith("/"):   # pomiń stronę-indeks sekcji
            continue
        out.append((prefix + rel, title))
    return out


def build_nav(prefix):
    items = []
    for label, href, section in NAV_TOP:
        top = f'<a href="{prefix}{href}">{html.escape(label)}</a>'
        kids = _nav_children(section, prefix) if section else []
        if kids:
            vis, extra = kids[:5], kids[5:]
            sub = "".join(
                f'<li><a href="{u}">{html.escape(t)}</a></li>' for u, t in vis)
            if extra:
                cid = f"m-{section}"
                extra_links = "".join(
                    f'<a href="{u}">{html.escape(t)}</a>' for u, t in extra)
                sub += (
                    f'<li class="sub-more-li">'
                    f'<input type="checkbox" id="{cid}" class="sub-more-cb" />'
                    f'<label for="{cid}" class="sub-more-btn">Więcej ({len(extra)})</label>'
                    f'<span class="sub-more">{extra_links}</span></li>')
            items.append(f'<li class="has-sub">{top}<ul class="sub">{sub}</ul></li>')
        else:
            items.append(f'<li>{top}</li>')
    items.append(
        f'<li><a class="nav-cta" href="{prefix}{NAV_CTA[1]}">{html.escape(NAV_CTA[0])}</a></li>')
    return (
        '<header class="site-header"><nav class="nav container">'
        f'<a class="logo" href="{prefix}index.html"><span class="logo-mark">≈</span><span>FishPoint</span></a>'
        '<button class="nav-toggle" aria-expanded="false" aria-controls="nav-menu">Menu</button>'
        f'<ul id="nav-menu" class="nav-menu">{"".join(items)}</ul></nav></header>')

title_re = re.compile(r"<title>(.*?)</title>", re.S)
desc_re = re.compile(r'<meta\s+name="description"\s+content="(.*?)"', re.S)
img_re = re.compile(r'<img[^>]+src="([^"]+)"', re.S)
block_re = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n", re.S)
tag_re = re.compile(r"<[^>]+>")

# Trwałe metadane redakcyjne są źródłem dat publikacji i aktualizacji. Nie
# należą do bloku seo:auto, aby ponowne uruchomienie generatora ich nie usuwało.
CONTENT_META_RE = re.compile(
    r"<!--content-meta:\s*published=(\d{4}-\d{2}-\d{2});\s*modified=(\d{4}-\d{2}-\d{2})-->",
)
CONTENT_META_MARKER_RE = re.compile(r"<!--\s*content-meta:", re.I)
robots_meta_re = re.compile(
    r'<meta\b(?=[^>]*\bname\s*=\s*["\']robots["\'])[^>]*>\s*', re.I)
youtube_nocookie_iframe_re = re.compile(
    r'''<iframe\b(?=[^>]*\bsrc\s*=\s*["']https?://(?:www\.)?youtube-nocookie\.com/embed/(?P<video_id>[A-Za-z0-9_-]{11})(?:\?[^"']*)?["'])(?=[^>]*\btitle\s*=\s*["'](?P<title>[^"']*)["'])[^>]*>\s*</iframe>''',
    re.I | re.S,
)


def replace_youtube_nocookie_embeds(src):
    """Zastępuje tylko znane iframe'y YouTube fasadą bez ładowania odtwarzacza."""
    def repl(match):
        video_id = match.group("video_id")
        title = html.unescape(match.group("title").strip()) or "Film YouTube"
        title_attr = html.escape(title, quote=True)
        return (
            f'<button class="youtube-facade" type="button" data-video-id="{video_id}" '
            f'data-video-title="{title_attr}" aria-label="Odtwórz film: {title_attr}">'
            f'<img src="https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" '
            f'alt="Miniatura filmu: {title_attr}" loading="lazy" decoding="async" />'
            f'<span class="youtube-facade-play" aria-hidden="true">▶</span>'
            f'<span class="youtube-facade-title">{html.escape(title)}</span>'
            f'</button>'
        )

    return youtube_nocookie_iframe_re.sub(repl, src)


def parse_content_meta(src, path):
    """Odczytuje dokładnie jeden poprawny komentarz content-meta."""
    matches = CONTENT_META_RE.findall(src)
    if len(matches) != 1:
        raise ValueError(f"{path}: oczekiwano dokładnie jednego content-meta")
    published, modified = matches[0]
    try:
        published_date = datetime.date.fromisoformat(published)
        modified_date = datetime.date.fromisoformat(modified)
    except ValueError as exc:
        raise ValueError(f"{path}: nieprawidłowa data content-meta") from exc
    if modified_date < published_date:
        raise ValueError(f"{path}: modified jest wcześniejsze niż published")
    return published, modified


def ensure_content_meta(src, path):
    """Dodaje komentarz tylko do starszych stron bez content-meta."""
    if CONTENT_META_MARKER_RE.search(src):
        return src, *parse_content_meta(src, path)
    published, modified = git_dates(path)
    comment = f"  <!--content-meta: published={published}; modified={modified}-->\n"
    src, count = re.subn(r"(<head\b[^>]*>\s*)", r"\1" + comment, src, count=1)
    if count != 1:
        raise ValueError(f"{path}: brak znacznika <head> dla content-meta")
    return src, published, modified


def is_noindex(src):
    """Czy dowolny meta robots strony jawnie wymaga noindex."""
    return any(
        re.search(r'\bnoindex\b', tag, re.I)
        for tag in robots_meta_re.findall(src)
    )

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
CONTENT_ADVANTAGE_BEGIN, CONTENT_ADVANTAGE_END = (
    "<!--content-advantage:auto-->",
    "<!--/content-advantage:auto-->",
)
content_advantage_re = re.compile(
    re.escape(CONTENT_ADVANTAGE_BEGIN) + r".*?" + re.escape(CONTENT_ADVANTAGE_END),
    re.S,
)
AFFILIATE_BEGIN, AFFILIATE_END = "<!--affiliate:auto-->", "<!--/affiliate:auto-->"
affiliate_re = re.compile(
    re.escape(AFFILIATE_BEGIN) + r".*?" + re.escape(AFFILIATE_END),
    re.S,
)

# „Metoda FishPoint” trafia wyłącznie na strony wyliczone poniżej. Pole
# author_practice_confirmed jest celowe: bez niego tekst nie może sugerować
# osobistych testów autora.
FISHPOINT_METHODS = {
    "techniki/spinning.html": {
        "practice": "Dobór przynęty i tempo prowadzenia traktuj jako punkt wyjścia do obserwacji własnej wody.",
        "facts": "Skuteczność zależy między innymi od pory roku, warunków i zachowania ryb.",
        "limits": "Opis nie gwarantuje brań; zasady połowu sprawdzaj w regulaminie łowiska.",
    },
    "poradniki/kalendarz-bran-szczupak.html": {
        "practice": "Kalendarz wykorzystaj do zaplanowania wyprawy, a pierwsze decyzje oprzyj na obserwacji łowiska.",
        "facts": "Aktywność szczupaka zmienia się wraz z warunkami wody i pogodą.",
        "limits": "To orientacyjny punkt odniesienia, nie prognoza brań ani źródło zasad połowu.",
    },
    "poradniki/kalendarz-bran-sandacz.html": {
        "practice": "Kalendarz wykorzystaj do zaplanowania pory i miejsca połowu, a taktykę dopasuj nad wodą.",
        "facts": "Aktywność sandacza zależy od warunków wody, pory dnia i presji na łowisku.",
        "limits": "To orientacyjny punkt odniesienia, nie prognoza brań ani źródło zasad połowu.",
    },
    "poradniki/kalendarz-bran-okon.html": {
        "practice": "Kalendarz wykorzystaj do wyboru terminu, a wielkość przynęty dopasuj do sytuacji na łowisku.",
        "facts": "Aktywność okonia zmienia się z porą roku, temperaturą wody i dostępnością pokarmu.",
        "limits": "To orientacyjny punkt odniesienia, nie prognoza brań ani źródło zasad połowu.",
    },
    "poradniki/etyka-i-przepisy.html": {
        "practice": "Przed wyprawą przygotuj dokumenty i sprawdź zasady dla konkretnej wody.",
        "facts": "Obowiązujące wymagania wynikają z przepisów oraz regulaminu łowiska.",
        "limits": "Materiał edukacyjny nie zastępuje aktualnego regulaminu, zezwolenia ani wykładni prawa.",
    },
    "zgodnie-z-zasadami.html": {
        "practice": "Przed wyprawą sprawdź zasady dla konkretnej wody i zachowaj ich aktualną wersję.",
        "facts": "Znaczenie mają przepisy, regulamin łowiska i warunki zezwolenia.",
        "limits": "Materiał edukacyjny nie zastępuje aktualnych źródeł ani wykładni prawa.",
    },
    "narzedzia/okresy-ochronne.html": {
        "practice": "Wynik tabeli porównaj z regulaminem wody, na której zamierzasz łowić.",
        "facts": "Wymiary, okresy i limity mogą różnić się między wodami.",
        "limits": "Tabela jest pomocą informacyjną, nie potwierdzeniem legalności połowu.",
    },
    "narzedzia/czy-moge-zabrac-rybe.html": {
        "practice": "Wynik kalkulatora porównaj z regulaminem i zezwoleniem dla konkretnej wody.",
        "facts": "Zasady mogą być zaostrzone przez gospodarza łowiska.",
        "limits": "Wynik jest orientacyjny i nie zastępuje aktualnych źródeł zasad połowu.",
    },
    "aktualnosci/wymiary-i-okresy-ochronne-2026.html": {
        "practice": "Przed wyjazdem porównaj zestawienie z aktualnym regulaminem konkretnej wody i zezwoleniem.",
        "facts": "Ogólnopolskie przepisy nie wyczerpują zasad ustanawianych lokalnie przez gospodarza łowiska.",
        "limits": "Tabela ma charakter pomocniczy; wiążące są aktualne przepisy i lokalny regulamin.",
    },
    "aktualnosci/gorne-wymiary-ochronne-2026.html": {
        "practice": "Górny wymiar traktuj jako zasadę konkretnej wody, którą trzeba potwierdzić przed wyprawą.",
        "facts": "Górne wymiary mogą wynikać z lokalnego regulaminu lub zezwolenia, a nie z ogólnej tabeli.",
        "limits": "Nie zakładaj obowiązywania tej zasady na innym łowisku bez sprawdzenia źródła.",
    },
    "pierwsze-kroki/okresy-ochronne-wymiary.html": {
        "practice": "Przed zabraniem ryby sprawdź gatunek, wymiar, okres oraz limity w aktualnych źródłach.",
        "facts": "Regulamin konkretnej wody może zaostrzać zasady ogólnopolskie.",
        "limits": "Materiał edukacyjny nie zastępuje aktualnego regulaminu ani zezwolenia.",
    },
    "pierwsze-kroki/pozwolenia-karta-wedkarska.html": {
        "practice": "Najpierw ustal gospodarza wody, potem kup właściwe zezwolenie i sprawdź jego warunki.",
        "facts": "Karta wędkarska, zezwolenie i regulamin łowiska to odrębne wymagania.",
        "limits": "Wymagania zależą od rodzaju wody i gospodarza; nie uogólniaj zasad jednego okręgu.",
    },
}

# Etykiety są jawnie przypisane do slugów; nie wynikają z daty publikacji ani
# aktualizacji artykułu.
SEASONAL_ARTICLE_LABELS = {
    "techniki/spinning.html": "Sezon jesienny 2026",
    "poradniki/kalendarz-bran-szczupak.html": "Sezon jesienny 2026",
    "poradniki/kalendarz-bran-sandacz.html": "Sezon jesienny 2026",
    "poradniki/kalendarz-bran-okon.html": "Sezon jesienny 2026",
}

FISHPOINT_METHOD_BEGIN, FISHPOINT_METHOD_END = (
    "<!--fishpoint-method:auto-->",
    "<!--/fishpoint-method:auto-->",
)
fishpoint_method_re = re.compile(
    re.escape(FISHPOINT_METHOD_BEGIN) + r".*?" + re.escape(FISHPOINT_METHOD_END),
    re.S,
)


def build_fishpoint_method(rel, config):
    """Buduje blok wiarygodności tylko z jawnej konfiguracji artykułu."""
    practice_label = (
        "Praktyka autora" if config.get("author_practice_confirmed")
        else "Wskazówki praktyczne"
    )
    season = SEASONAL_ARTICLE_LABELS.get(rel)
    season_html = (
        f'<p class="badge fishpoint-method-season">{html.escape(season)}</p>'
        if season else ""
    )
    return (
        f'{FISHPOINT_METHOD_BEGIN}<section class="info-block fishpoint-method" '
        f'aria-label="Metoda FishPoint">{season_html}<h2>Metoda FishPoint</h2>'
        f'<p><strong>{practice_label}:</strong> {html.escape(config["practice"])}</p>'
        f'<p><strong>Fakty:</strong> {html.escape(config["facts"])}</p>'
        f'<p><strong>Ograniczenia:</strong> {html.escape(config["limits"])}</p>'
        f'</section>{FISHPOINT_METHOD_END}'
    )


def inject_fishpoint_method(src, rel):
    """Wstawia blok po TL;DR, a bez TL;DR na początku treści artykułu."""
    config = FISHPOINT_METHODS.get(rel)
    if not config:
        return src
    method = build_fishpoint_method(rel, config)
    if TLDR_END in src:
        return src.replace(TLDR_END, TLDR_END + method, 1)
    return re.sub(
        r'(<article\b(?=[^>]*\bclass="[^"]*\barticle-card\b)[^>]*>|'
        r'<section\b(?=[^>]*\bclass="[^"]*\barticle-section\b)[^>]*>)',
        r"\1" + method,
        src,
        count=1,
    )

# Krótkie moduły odpowiedzi dla stron, na których użytkownik zwykle zaczyna
# konkretną decyzję. Wszystkie odnośniki są lokalne i przed renderem dodatkowo
# sprawdzane względem katalogu projektu.
CONTENT_ADVANTAGES = {
    "index.html": {
        "answer": "Na start wybierz prostą ścieżkę: poznaj formalności, skompletuj podstawowy zestaw i zaplanuj łatwy pierwszy wyjazd. Nie musisz podejmować wszystkich decyzji naraz.",
        "table": ("Od czego zacząć", ("Etap", "Co ustalić", "Następny krok"), (
            ("1. Zasady", "Kto zarządza wybraną wodą i jakie dokumenty obowiązują.", "Sprawdź formalności."),
            ("2. Zestaw", "Jaką metodą chcesz zacząć i co jest do niej niezbędne.", "Wybierz podstawowy komplet."),
            ("3. Wyjazd", "Gdzie bezpiecznie stanąć i co zabrać.", "Przejdź checklistę."),
        )),
        "mistakes": ("Kupowanie przypadkowych akcesoriów przed wyborem metody.", "Traktowanie jednego regulaminu jako zasad dla wszystkich wód.", "Odkładanie przygotowania pierwszego wyjazdu na ostatnią chwilę."),
        "method": "To mapa tematów, nie lista obowiązkowych zakupów ani obietnica wyniku nad wodą.",
        "source_prompt": "Przy zasadach połowu zawsze porównaj poradnik z aktualnym zezwoleniem i regulaminem gospodarza wody.",
        "links": (("/pierwsze-kroki/index.html", "Przewodnik dla początkujących"), ("/pierwsze-kroki/pozwolenia-karta-wedkarska.html", "Dokumenty i zezwolenia"), ("/pierwsze-kroki/twoj-pierwszy-wyjazd-na-ryby.html", "Pierwszy wyjazd")),
    },
    "pierwsze-kroki/index.html": {
        "answer": "Najpierw sprawdź zasady dla wody, na którą chcesz jechać. Potem wybierz prosty zestaw i przygotuj pierwszy wyjazd z krótką listą rzeczy do zabrania.",
        "table": ("Plan początkującego", ("Kolejność", "Decyzja", "Po czym poznać, że możesz iść dalej"), (
            ("Formalności", "Ustal gospodarza wody i wymagane dokumenty.", "Masz aktualne zezwolenie oraz regulamin."),
            ("Sprzęt", "Dobierz zestaw do wybranej metody.", "Wiesz, jak go bezpiecznie złożyć."),
            ("Woda", "Wybierz miejsce z bezpiecznym dostępem.", "Masz plan stanowiska i powrotu."),
        )),
        "mistakes": ("Porównywanie sprzętu bez określenia metody połowu.", "Mylenie karty wędkarskiej z zezwoleniem konkretnego gospodarza.", "Pakowanie bez miarki, narzędzia do odhaczania i zapasu wody."),
        "method": "Kolejne artykuły rozdzielają decyzje sprzętowe, organizacyjne i regulaminowe, aby można było sprawdzić każdą z nich osobno.",
        "source_prompt": "Regulamin i warunki zezwolenia dla konkretnej wody mają pierwszeństwo przed ogólną poradą.",
        "links": (("/pierwsze-kroki/pierwszy-zestaw-wedkarski-budzet.html", "Pierwszy zestaw"), ("/pierwsze-kroki/pozwolenia-karta-wedkarska.html", "Pozwolenia i karta"), ("/pierwsze-kroki/twoj-pierwszy-wyjazd-na-ryby.html", "Plan pierwszego wyjazdu")),
    },
    "techniki/spinning.html": {
        "answer": "W spinningu zacznij od bezpiecznego stanowiska, jednej prostej przynęty i spokojnego prowadzenia. Zmieniaj tylko jeden element naraz, aby widzieć, co wynika z warunków.",
        "table": ("Pierwsza decyzja spinningowa", ("Sytuacja", "Punkt wyjścia", "Co obserwować"), (
            ("Nieznana woda", "Zacznij od krótkiego odcinka i czytaj brzeg.", "Przejścia głębokości, nurt i przeszkody."),
            ("Brak kontaktu", "Zmień tempo albo głębokość prowadzenia.", "Czy przynęta pracuje tam, gdzie zakładasz."),
            ("Kontakt z rybą", "Nie przyspieszaj kolejnych zmian.", "Miejsce, porę i powtarzalność sygnałów."),
        )),
        "mistakes": ("Zbyt wiele zmian przynęt bez obserwacji miejsca.", "Rzuty w nieznane przeszkody bez oceny dostępu i bezpieczeństwa.", "Traktowanie opisu techniki jako gwarancji brań."),
        "spot": ("Czytanie miejsca przed rzutem", ("Sprawdź, czy dojście i brzeg są bezpieczne.", "Zauważ granice roślinności, wypłycenia, nurt lub widoczne przeszkody.", "Wybierz kierunek rzutu, który pozwala bezpiecznie poprowadzić i odzyskać przynętę.")),
        "method": "Opis daje punkt startowy do obserwacji własnej wody; dobór prowadzenia zależy od sytuacji nad wodą.",
        "source_prompt": "Przed łowieniem sprawdź ograniczenia metody, gatunku i miejsca w aktualnym regulaminie.",
        "links": (("/pierwsze-kroki/sprzet/wedki.html", "Wędka dla początkującego"), ("/pierwsze-kroki/sprzet/przynety.html", "Przynęty od podstaw"), ("/pierwsze-kroki/okresy-ochronne-wymiary.html", "Okresy i wymiary")),
    },
    "pierwsze-kroki/pierwszy-zestaw-wedkarski-budzet.html": {
        "answer": "Pierwszy zestaw ma pozwolić bezpiecznie zacząć, a nie pokryć każdą metodę. Najpierw wybierz wodę i sposób łowienia, później ogranicz zakupy do rzeczy potrzebnych na pierwszy wyjazd.",
        "table": ("Budżet 200–300 zł: orientacyjny podział", ("Obszar", "Punkt wyjścia", "Na czym nie oszczędzać"), (
            ("Wędka", "Około jednej trzeciej budżetu.", "Wygodzie, dopasowaniu do metody i bezpiecznym c.w."),
            ("Kołowrotek", "Około jednej trzeciej budżetu.", "Płynnej pracy hamulca i zgodności z wędką."),
            ("Linka, drobnica, przynęty", "Pozostała część budżetu.", "Miarce, narzędziu do odhaczania i rzeczach potrzebnych na wyjazd."),
        )),
        "mistakes": ("Wydawanie całego budżetu na jeden element zestawu.", "Kupowanie przynęt bez planu pierwszej metody.", "Pomijanie miarki i narzędzia do bezpiecznego odhaczania."),
        "method": "To orientacyjny podział opisany w poradniku, a nie bieżąca wycena ani ranking produktów; ceny zmieniają się między sklepami i sezonami.",
        "source_prompt": "Przed zakupem porównaj proporcje z aktualnymi ofertami i planowaną metodą łowienia.",
        "links": (("/pierwsze-kroki/sprzet/wedki.html", "Jak wybrać wędkę"), ("/pierwsze-kroki/sprzet/przynety.html", "Jak dobrać przynęty"), ("/pierwsze-kroki/twoj-pierwszy-wyjazd-na-ryby.html", "Co spakować na pierwszy wyjazd")),
    },
    "pierwsze-kroki/sprzet/wedki.html": {
        "answer": "Wędkę dobieraj najpierw do miejsca i metody, a dopiero później do marki czy dodatków. Oznaczenia długości i ciężaru wyrzutowego mają pomóc porównać zastosowanie, nie zastępują dopasowania całego zestawu.",
        "table": ("Jak zawęzić wybór wędki", ("Pytanie", "Co sprawdzić", "Decyzja na start"), (
            ("Gdzie będziesz łowić?", "Miejsce, dostęp do brzegu i przestrzeń do rzutu.", "Wybierz rozwiązanie wygodne w tych warunkach."),
            ("Jaką metodą?", "Typ przynęty lub zestawu oraz zakres jego użycia.", "Dopasuj oznaczenia wędziska do metody."),
            ("Z czym ją połączysz?", "Kołowrotek, linkę i podstawowe akcesoria.", "Oceń zestaw jako całość, nie sam blank."),
        )),
        "mistakes": ("Wybór wyłącznie po nazwie marki lub wyglądzie.", "Ignorowanie ciężaru używanych przynęt albo zestawu.", "Kupowanie bez sprawdzenia wygody chwytu i transportu."),
        "method": "Podane kryteria pomagają zadawać właściwe pytania; nie są testem konkretnego modelu ani rekomendacją zakupu.",
        "source_prompt": "Przed zakupem porównaj opis producenta z planowaną metodą i warunkami własnych łowisk.",
        "links": (("/pierwsze-kroki/sprzet/kolowrotki.html", "Kołowrotki dla początkujących"), ("/pierwsze-kroki/sprzet/zylki-plecionki.html", "Żyłka i plecionka"), ("/pierwsze-kroki/pierwszy-zestaw-wedkarski-budzet.html", "Kompletowanie pierwszego zestawu")),
    },
    "pierwsze-kroki/sprzet/przynety.html": {
        "answer": "Zacznij od kilku przynęt pasujących do wybranej metody i ucz się ich prowadzenia w jednym miejscu. Wielkość pudełka nie zastępuje obserwacji warunków ani sprawdzenia zasad łowiska.",
        "table": ("Dobór przynęty: prosty filtr", ("Pytanie", "Sprawdź", "Co zrobić dalej"), (
            ("Jaka metoda?", "Czy przynęta pasuje do używanego zestawu.", "Wybierz kilka wariantów, nie cały katalog."),
            ("Jakie miejsce?", "Głębokość, przeszkody i możliwość bezpiecznego prowadzenia.", "Dopasuj sposób prowadzenia do odcinka."),
            ("Jakie zasady?", "Regulamin wody i ochronę gatunków.", "Nie kieruj połowu na gatunek objęty ograniczeniem."),
        )),
        "mistakes": ("Zmiana przynęty po każdym rzucie bez oceny miejsca.", "Dobieranie przynęty bez sprawdzenia, czy zestaw ją obsłuży.", "Kierowanie połowu na gatunek, którego zasady nie zostały sprawdzone."),
        "method": "Przynęta jest jednym z elementów decyzji; poradnik nie przewiduje brań ani nie zastępuje oceny warunków.",
        "source_prompt": "Dla wybranej wody zweryfikuj aktualne ograniczenia metod i gatunków przed wyjazdem.",
        "links": (("/techniki/spinning.html", "Podstawy spinningu"), ("/pierwsze-kroki/sprzet/wedki.html", "Dobór wędki"), ("/pierwsze-kroki/okresy-ochronne-wymiary.html", "Zasady ochrony ryb")),
    },
    "ryby/szczupak.html": {
        "answer": "Opis szczupaka pomaga rozpoznać gatunek i zaplanować obserwację miejsca. Przed celowym połowem sprawdź aktualne zasady ochrony oraz regulamin konkretnej wody.",
        "table": ("Plan obserwacji szczupaka", ("Sygnał miejsca", "Co zanotować", "Bezpieczny następny krok"), (
            ("Roślinność i osłony", "Dostęp do brzegu i możliwą drogę holu.", "Nie rzucaj tam, gdzie nie odzyskasz przynęty bez ryzyka."),
            ("Zmiana głębokości", "Widoczne krawędzie i przejścia.", "Prowadź przynętę pod kontrolą."),
            ("Kontakt z rybą", "Miejsce i warunki, bez uogólniania na całą wodę.", "Sprawdź, czy połów gatunku jest dozwolony."),
        )),
        "mistakes": ("Mylenie rozpoznania gatunku z potwierdzeniem, że można go zabrać.", "Łowienie bez sprawdzenia okresu ochronnego i lokalnych ograniczeń.", "Próba holu w miejscu bez bezpiecznego dostępu do brzegu."),
        "spot": ("Checklist miejsca", ("Sprawdź bezpieczne dojście i wyjście ze stanowiska.", "Szukaj zmian roślinności, głębokości lub osłon widocznych z brzegu.", "Zaplanuj, gdzie bezpiecznie odhaczysz i wypuścisz rybę.")),
        "method": "Informacje gatunkowe są punktem do nauki rozpoznawania i obserwacji, nie prognozą skuteczności.",
        "source_prompt": "Decyzję o połowie i zabraniu ryby oprzyj na aktualnym zezwoleniu, regulaminie oraz zasadach ochrony.",
        "links": (("/techniki/spinning.html", "Spinning krok po kroku"), ("/pierwsze-kroki/okresy-ochronne-wymiary.html", "Okresy ochronne i wymiary"), ("/ryby/okon.html", "Jak rozpoznać okonia")),
    },
    "ryby/okon.html": {
        "answer": "Opis okonia służy rozpoznaniu gatunku i obserwacji miejsca. To, czy i jak możesz łowić, zawsze zależy od aktualnych zasad dla konkretnej wody.",
        "table": ("Plan obserwacji okonia", ("Sygnał miejsca", "Co zanotować", "Następny krok"), (
            ("Zmiana dna lub osłona", "Bezpieczny tor prowadzenia i zaczepy.", "Prowadź przynętę w kontrolowanym tempie."),
            ("Kilka kontaktów", "Odcinek, głębokość i warunki.", "Zmieniaj jeden element naraz."),
            ("Ryba przy brzegu", "Możliwość bezpiecznego podjęcia i wypuszczenia.", "Przygotuj narzędzie do odhaczania."),
        )),
        "mistakes": ("Wnioskowanie o całym łowisku po jednym kontakcie.", "Brak narzędzia do sprawnego odhaczania.", "Pomijanie identyfikacji ryby przed decyzją o jej zabraniu."),
        "spot": ("Checklist miejsca", ("Oceń bezpieczny dostęp do brzegu.", "Zauważ widoczne przeszkody i różnice w strukturze wody.", "Wybierz tor rzutu, który pozwala kontrolować przynętę i powrót.")),
        "method": "Wskazówki opisują sposób obserwacji, nie obiecują wyniku ani nie zastępują znajomości lokalnego łowiska.",
        "source_prompt": "Wymiary, limity i lokalne zasady sprawdź w aktualnym zezwoleniu przed decyzją o zabraniu ryby.",
        "links": (("/techniki/spinning.html", "Podstawy spinningu"), ("/pierwsze-kroki/sprzet/przynety.html", "Przynęty dla początkujących"), ("/pierwsze-kroki/okresy-ochronne-wymiary.html", "Wymiary i limity")),
    },
    "ryby/sandacz.html": {
        "answer": "Opis sandacza ma pomóc odróżnić gatunek i ułożyć obserwację miejsca. Nie jest wskazaniem terminu połowu ani potwierdzeniem, że dany gatunek można w tym momencie łowić.",
        "table": ("Plan obserwacji sandacza", ("Sygnał miejsca", "Co sprawdzić", "Następny krok"), (
            ("Zmiana głębokości", "Czy możesz bezpiecznie kontrolować kontakt z przynętą.", "Obserwuj prowadzenie, nie tylko sam rzut."),
            ("Twardsze lub miękkie dno", "Powtarzalność odczucia na krótkim odcinku.", "Zmieniaj tempo pojedynczo."),
            ("Ryba przy brzegu", "Miejsce do bezpiecznego odhaczenia.", "Przygotuj wypuszczenie przed podjęciem ryby."),
        )),
        "mistakes": ("Traktowanie kalendarza lub opisu gatunku jako prognozy brań.", "Zaniedbanie aktualnej ochrony gatunku.", "Prowadzenie przynęty bez kontroli nad zaczepami i głębokością."),
        "spot": ("Checklist miejsca", ("Sprawdź stabilne i bezpieczne stanowisko.", "Szukaj czytelnych przejść głębokości lub zmian dna, jeśli są widoczne lub wyczuwalne.", "Notuj warunki oraz miejsce kontaktu zamiast zakładać stały schemat.")),
        "method": "Opis gatunku porządkuje obserwację, ale skuteczność i zasady zależą od warunków oraz aktualnych regulaminów.",
        "source_prompt": "Przed wyprawą sprawdź aktualny okres ochronny, warunki zezwolenia i lokalne ograniczenia dla wybranej wody.",
        "links": (("/techniki/spinning.html", "Spinning od podstaw"), ("/poradniki/kalendarz-bran-sandacz.html", "Kalendarz brań sandacza"), ("/pierwsze-kroki/okresy-ochronne-wymiary.html", "Ochrona ryb")),
    },
    "pierwsze-kroki/pozwolenia-karta-wedkarska.html": {
        "answer": "Karta wędkarska, zezwolenie i regulamin to różne elementy. Przed wyjazdem ustal gospodarza wybranej wody, sprawdź wymagane dokumenty i przeczytaj aktualne warunki zezwolenia.",
        "table": ("Formalności przed wyjazdem", ("Pytanie", "Gdzie sprawdzić", "Co zachować"), (
            ("Kto zarządza wodą?", "W dokumentach i informacji gospodarza.", "Nazwę wody oraz zakres zezwolenia."),
            ("Jakie dokumenty obowiązują?", "W aktualnych warunkach gospodarza.", "Dokumenty wymagane podczas kontroli."),
            ("Jakie ograniczenia są lokalne?", "W regulaminie i wykazie wód.", "Wersję obowiązującą na dzień wyjazdu."),
        )),
        "mistakes": ("Traktowanie karty jako zezwolenia na każdą wodę.", "Korzystanie z nieaktualnej informacji o warunkach.", "Pomijanie regulaminu dlatego, że miejsce było już odwiedzane."),
        "method": "To porządek sprawdzania informacji, nie wykładnia prawa ani potwierdzenie uprawnień dla konkretnej osoby lub wody.",
        "source_prompt": "W sprawach formalnych wiążące są aktualne dokumenty gospodarza i właściwe źródła urzędowe wskazane w artykule.",
        "links": (("/pierwsze-kroki/okresy-ochronne-wymiary.html", "Okresy, wymiary i limity"), ("/zgodnie-z-zasadami.html", "Przepisy i dokumenty"), ("/pierwsze-kroki/twoj-pierwszy-wyjazd-na-ryby.html", "Checklist pierwszego wyjazdu")),
    },
    "pierwsze-kroki/okresy-ochronne-wymiary.html": {
        "answer": "Przed decyzją o zabraniu ryby sprawdź jej gatunek, wymiar, aktualny okres ochronny, limit oraz regulamin konkretnej wody. Gdy wynik jest niepewny, nie ryzykuj i zweryfikuj źródło.",
        "table": ("Kontrola przed zabraniem ryby", ("Krok", "Co sprawdzić", "Bezpieczna decyzja"), (
            ("Rozpoznanie", "Gatunek i cechy pozwalające go odróżnić.", "Przy wątpliwości nie zabieraj ryby."),
            ("Pomiar", "Wymiar zgodnie z zasadami danej wody.", "Użyj miarki i nie szacuj na oko."),
            ("Regulamin", "Okres, limit i ewentualne zaostrzenia lokalne.", "Porównaj z aktualnym zezwoleniem."),
        )),
        "mistakes": ("Mierzenie ryby bez miarki.", "Stosowanie ogólnej tabeli bez sprawdzenia lokalnych zaostrzeń.", "Zakładanie, że brak pewności usprawiedliwia zatrzymanie ryby."),
        "method": "Tabela i poradnik mają charakter edukacyjny; nie zastępują aktualnego zezwolenia, regulaminu ani źródeł prawa.",
        "source_prompt": "Najpierw korzystaj z aktualnego regulaminu gospodarza wody i dokumentów wskazanych w sekcji źródeł artykułu.",
        "links": (("/pierwsze-kroki/pozwolenia-karta-wedkarska.html", "Karta i zezwolenia"), ("/zgodnie-z-zasadami.html", "Przepisy i dokumenty"), ("/pierwsze-kroki/jak-nabic-przynete-i-odhaczyc-rybe.html", "Bezpieczne odhaczanie")),
    },
    "pierwsze-kroki/twoj-pierwszy-wyjazd-na-ryby.html": {
        "answer": "Na pierwszy wyjazd wybierz prostą wodę z bezpiecznym dostępem, spakuj tylko potrzebny zestaw i sprawdź dokumenty przed wyjściem. Nad wodą zaczynaj spokojnie: bezpieczeństwo i zasady są ważniejsze niż tempo.",
        "table": ("Pierwszy wyjazd: plan minimum", ("Moment", "Co zrobić", "Po co"), (
            ("Przed wyjazdem", "Sprawdź pogodę, dojazd, zasady i dokumenty.", "Uniknąć organizacyjnych niespodzianek."),
            ("Przed rozłożeniem sprzętu", "Oceń brzeg, dojście i miejsce do odhaczania.", "Zachować bezpieczeństwo własne i ryby."),
            ("Po zakończeniu", "Zabierz odpady i sprawdź, czy nic nie zostało.", "Zostawić stanowisko w porządku."),
        )),
        "mistakes": ("Wybór stanowiska bez sprawdzenia bezpiecznego dojścia.", "Pakowanie sprzętu bez dokumentów i miarki.", "Wchodzenie do wody lub na śliski brzeg tylko po to, by odzyskać przynętę."),
        "spot": ("Checklist stanowiska", ("Czy możesz stabilnie dojść, stanąć i wrócić po zmroku lub zmianie pogody?", "Czy masz miejsce, aby bezpiecznie przygotować sprzęt i odhaczyć rybę?", "Czy wiesz, gdzie kończy się bezpieczny brzeg oraz których przeszkód unikać?")),
        "method": "Lista pomaga uporządkować przygotowanie, ale nie zastępuje oceny warunków na miejscu ani zasad gospodarza wody.",
        "source_prompt": "Przed wyjazdem porównaj własny plan z aktualnym zezwoleniem, regulaminem i komunikatami dla wybranego łowiska.",
        "links": (("/pierwsze-kroki/pierwszy-zestaw-wedkarski-budzet.html", "Pierwszy zestaw"), ("/pierwsze-kroki/pozwolenia-karta-wedkarska.html", "Dokumenty przed wyjazdem"), ("/pierwsze-kroki/jak-nabic-przynete-i-odhaczyc-rybe.html", "Odhaczanie ryby")),
    },
    "techniki/feeder-dla-poczatkujacych.html": {
        "answer": "Na pierwszy feeder wybierz prostą wodę, jeden zestaw i koszyk dopasowany do warunków. Najpierw ustal miejsce i metodę, dopiero potem kupuj elementy.",
        "table": ("Feeder na start", ("Decyzja", "Punkt wyjścia", "Co sprawdzić"), (
            ("Woda", "Spokojny brzeg z bezpiecznym dostępem.", "Czy możesz powtarzalnie rzucać i odhaczyć rybę."),
            ("Zestaw", "Wędka, kołowrotek, linka i bezpieczny montaż.", "Czy masa koszyka z zanętą mieści się w zakresie wędki."),
            ("Taktyka", "Jeden punkt i małe, regularne porcje.", "Czy zestaw leży stabilnie i pokazuje branie."),
        )),
        "mistakes": ("Kupowanie ciężkiego zestawu bez określenia wody.", "Zbyt mokra albo zbyt sucha zanęta.", "Zmienianie miejsca, koszyka i przynęty jednocześnie."),
        "method": "Poradnik ogranicza decyzje do pierwszego wyjazdu; nie jest rankingiem produktów ani obietnicą brań.",
        "source_prompt": "Parametry sprzętu porównaj z kartą producenta, a zasady metody z aktualnym regulaminem gospodarza wody.",
        "links": (("/techniki/feeder.html", "Pełny poradnik feederowy"), ("/pierwsze-kroki/sprzet/wedki.html", "Wybór wędki"), ("/pierwsze-kroki/sprzet/kolowrotki.html", "Dobór kołowrotka")),
    },
    "aktualnosci/jak-lowic-leszcza.html": {
        "answer": "Leszcza szukaj przy powtarzalnej krawędzi dna lub spokojniejszej wodzie. Zacznij od feedera albo spławika, małych porcji zanęty i jednej kontrolowanej przynęty.",
        "table": ("Plan łowienia leszcza", ("Etap", "Punkt wyjścia", "Co obserwować"), (
            ("Miejsce", "Krawędź, twardszy plac albo spokojniejsza woda.", "Czy możesz dokładnie powtarzać rzut."),
            ("Metoda", "Feeder na dystansie albo spławik w spokojnej wodzie.", "Stabilność zestawu i czytelność brania."),
            ("Nęcenie", "Małe, regularne porcje.", "Czy ryba zostaje w punkcie bez przeładowania."),
        )),
        "mistakes": ("Zakładanie, że najgłębsze miejsce jest zawsze najlepsze.", "Zasypywanie punktu zanętą.", "Zmienianie kilku elementów po jednym pustym rzucie."),
        "spot": ("Checklist miejsca", ("Sprawdź bezpieczne stanowisko.", "Znajdź punkt, który możesz powtarzalnie osiągnąć.", "Zapisz porę, odległość i warunki kontaktu.")),
        "method": "Opis porządkuje obserwację wody i nie zastępuje oceny warunków ani lokalnych zasad.",
        "source_prompt": "Rozpoznanie gatunku porównaj z atlasem, a ochronę i limity z aktualnym regulaminem konkretnej wody.",
        "links": (("/ryby/leszcz.html", "Leszcz w atlasie"), ("/techniki/feeder.html", "Feeder"), ("/techniki/splawik.html", "Spławik")),
    },
    "aktualnosci/jak-lowic-ploc.html": {
        "answer": "Płoci szukaj przy roślinności, spokojniejszej wodzie i granicy nurtu. Zacznij od czułego spławika albo lekkiego feedera, małych porcji i niewielkiej przynęty.",
        "table": ("Plan łowienia płoci", ("Sytuacja", "Punkt wyjścia", "Co sprawdzić"), (
            ("Woda stojąca", "Roślinność, zatoka albo płytsza półka.", "Czy zestaw pozostaje w aktywnej strefie."),
            ("Rzeka", "Spokojniejsza woda przy nurcie.", "Czy dryf nie wyprowadza przynęty z punktu."),
            ("Brania", "Jedna zmiana głębokości naraz.", "Czy ruch pokazuje rybę, a nie falę."),
        )),
        "mistakes": ("Używanie zbyt dużej przynęty bez obserwacji.", "Donęcanie dużymi porcjami.", "Zacinanie każdego ruchu spławika lub szczytówki."),
        "method": "To punkt startowy do nauki głębokości i prowadzenia, nie uniwersalny przepis na każdy akwen.",
        "source_prompt": "Gatunek porównaj z atlasem ryb, a zasady połowu z aktualnym regulaminem gospodarza wody.",
        "links": (("/ryby/ploc.html", "Płoć w atlasie"), ("/techniki/splawik.html", "Metoda spławikowa"), ("/poradniki/zanety-domowe.html", "Zanęty")),
    },
    "poradniki/wedkarstwo-z-brzegu.html": {
        "answer": "Najpierw wybierz legalny i bezpieczny dostęp, potem oceń dno, wiatr i możliwość powtarzalnego rzutu. Na pierwszy wyjazd zabierz jedną metodę i sprzęt do bezpiecznego odhaczania.",
        "table": ("Plan wyjazdu z brzegu", ("Krok", "Co ustalić", "Bezpieczna decyzja"), (
            ("Dostęp", "Właściciel terenu, gospodarz wody i dojście.", "Nie wchodź na niepewny lub śliski brzeg."),
            ("Warunki", "Wiatr, fala, nurt i droga powrotu.", "Zostaw zapas bezpieczeństwa."),
            ("Metoda", "Odległość i sposób prezentacji.", "Zacznij od jednego prostego zestawu."),
        )),
        "mistakes": ("Traktowanie publicznego brzegu jako automatycznie dostępnego.", "Wybieranie miejsca po reputacji zamiast warunkach.", "Brak planu odhaczenia i powrotu po zmroku."),
        "spot": ("Ocena stanowiska", ("Sprawdź stabilne dojście i miejsce do odhaczenia.", "Zobacz, czy możesz prowadzić zestaw bez wchodzenia do wody.", "Oceń wiatr, nurt i przeszkody przed pierwszym rzutem.")),
        "method": "Lista pomaga przygotować wyjazd, ale nie zastępuje oceny miejsca ani aktualnych dokumentów gospodarza.",
        "source_prompt": "Dostęp, zezwolenia i ograniczenia sprawdzaj w aktualnych informacjach gospodarza konkretnej wody.",
        "links": (("/pierwsze-kroki/twoj-pierwszy-wyjazd-na-ryby.html", "Pierwszy wyjazd"), ("/narzedzia/stany-wod.html", "Stany wód"), ("/lowiska/index.html", "Łowiska")),
    },
    "sprzet/jak-wybrac-kolowrotek.html": {
        "answer": "Kołowrotek dobierz do metody, wędki, linki i dystansu. Porównuj masę, pojemność szpuli, hamulec, przełożenie i nawój według karty konkretnego producenta.",
        "table": ("Wybór kołowrotka", ("Pytanie", "Co sprawdzić", "Decyzja"), (
            ("Jaka metoda?", "Spinning, feeder, spławik i sposób prowadzenia.", "Zawęź modele do konkretnego zastosowania."),
            ("Jaka linka?", "Średnica, długość i pojemność szpuli.", "Porównaj dane producenta, nie sam numer rozmiaru."),
            ("Jaka wędka?", "Masa, wyważenie i uchwyt.", "Połącz zestaw przed zakupem."),
        )),
        "mistakes": ("Wybór wyłącznie po numerze rozmiaru.", "Porównywanie maksymalnego hamulca bez testu jego pracy.", "Kupowanie bez sprawdzenia pojemności szpuli i masy zestawu."),
        "method": "Kryteria pomagają zawęzić wybór, ale nie są testem ani rekomendacją konkretnego modelu.",
        "source_prompt": "Parametry, kompatybilność i gwarancję sprawdzaj w karcie producenta oraz u sprzedawcy.",
        "links": (("/sprzet/kolowrotki.html", "Kołowrotki"), ("/pierwsze-kroki/sprzet/wedki.html", "Wędki"), ("/techniki/spinning.html", "Spinning")),
    },
}

AFFILIATE_LINKS = {
    "techniki/feeder-dla-poczatkujacych.html": (
        (
            "https://webep1.com/go/c4f3584fc3",
            "Kołowrotki feederowe",
            "Dobierz kołowrotek do wędki, koszyka i planowanego dystansu.",
        ),
        (
            "https://webep1.com/go/b371c4e1c3",
            "Wędki feederowe",
            "Porównaj feedery i pickery przed skompletowaniem zestawu.",
        ),
        (
            "https://webep1.com/go/bbf47570c3",
            "Koszyki feederowe",
            "Wybierz koszyk odpowiedni do zanęty, dna i siły nurtu.",
        ),
        (
            "https://webep1.com/go/fee88a95c3",
            "Zanęty",
            "Sprawdź zanęty, gliny i ziemie do przygotowania mieszanki.",
        ),
    ),
    "aktualnosci/jaka-wedka-spinningowa-kupic.html": (
        (
            "https://webep1.com/go/89081d9c3",
            "Wędki spinningowe",
            "Porównaj długości i ciężary wyrzutu pod okonia, szczupaka i sandacza.",
        ),
        (
            "https://webep1.com/go/f536215bc3",
            "Kołowrotki spinningowe",
            "Dobierz rozmiar i hamulec do planowanej wędki oraz przynęt.",
        ),
        (
            "https://webep1.com/go/9c39f3a6c3",
            "Plecionki spinningowe",
            "Sprawdź plecionki i średnice dopasowane do metody oraz łowiska.",
        ),
    ),
    "sprzet/jak-wybrac-kolowrotek.html": (
        (
            "https://webep1.com/go/f536215bc3",
            "Kołowrotki spinningowe",
            "Porównaj modele do lekkiego i cięższego spinningu.",
        ),
        (
            "https://webep1.com/go/c4f3584fc3",
            "Kołowrotki feederowe",
            "Sprawdź kołowrotki do feedera i method feeder.",
        ),
    ),
    "sprzet/plecionki-zylki.html": (
        (
            "https://webep1.com/go/e7918164c3",
            "Żyłki, plecionki i fluorocarbon",
            "Porównaj linki do spinningu i pozostałych metod.",
        ),
    ),
    "sprzet/przynety.html": (
        (
            "https://webep1.com/go/1a035dcfc3",
            "Przynęty sztuczne",
            "Zobacz gumy, woblery, błystki i inne przynęty na drapieżniki.",
        ),
        (
            "https://webep1.com/go/885f8602c3",
            "Gumy i rippery",
            "Sprawdź klasyczne kopyta i rippery do prowadzenia z opadu.",
        ),
    ),
    "aktualnosci/jak-dobrac-gume-na-drapieznika.html": (
        (
            "https://webep1.com/go/1a035dcfc3",
            "Przynęty sztuczne",
            "Porównaj gumy, woblery i błystki przed wyborem konkretnej przynęty.",
        ),
        (
            "https://webep1.com/go/885f8602c3",
            "Kopyta i rippery",
            "Sprawdź klasyczne gumy do łowienia sandacza i szczupaka.",
        ),
    ),
    "sprzet/akcesoria.html": (
        (
            "https://webep1.com/go/1bb1a3b3c3",
            "Akcesoria wędkarskie",
            "Uzupełnij zestaw o haki, agrafki, ciężarki i drobne wyposażenie.",
        ),
    ),
    "zakupy.html": (
        (
            "https://webep1.com/go/b39ea55c3",
            "Gotowy zestaw feederowy",
            "Porównaj gotowe zestawy feederowe, gdy chcesz zacząć bez kompletowania każdego elementu osobno.",
        ),
        (
            "https://webep1.com/go/92f2af80c3",
            "Gotowy zestaw method feeder",
            "Sprawdź gotowe zestawy method feeder do łowienia z koszykiem i zanętą.",
        ),
        (
            "https://webep1.com/go/fe23f399c3",
            "Gotowy zestaw spinningowy",
            "Zobacz gotowe zestawy spinningowe na pierwsze wyprawy za drapieżnikami.",
        ),
        (
            "https://webep1.com/go/86ac9324c3",
            "Kołowrotki karpiowe",
            "Porównaj kołowrotki karpiowe dopasowane do cięższych zestawów i dużych dystansów.",
        ),
        (
            "https://webep1.com/go/9ce264e7c3",
            "Wędki karpiowe",
            "Wybierz wędki karpiowe pod długość rzutu, ciężar zestawu i sposób łowienia.",
        ),
        (
            "https://webep1.com/go/6ff7647bc3",
            "Kulki i pellety",
            "Sprawdź kulki proteinowe i pellety do budowania zanęty oraz przynęty.",
        ),
        (
            "https://webep1.com/go/c8227fd2c3",
            "Dodatki zanętowe i dipy",
            "Dobierz dodatki zanętowe i dipy do mieszanki, przynęty oraz warunków łowiska.",
        ),
        (
            "https://webep1.com/go/d3253924c3",
            "Woblery",
            "Porównaj woblery na drapieżniki według pracy, głębokości i sposobu prowadzenia.",
        ),
        (
            "https://webep1.com/go/405fc98ac3",
            "Błystki",
            "Zobacz błystki do aktywnego szukania okoni, szczupaków i innych drapieżników.",
        ),
        (
            "https://webep1.com/go/4d1297a8c3",
            "Twistery",
            "Wybierz twistery do jigowania i prowadzenia przy dnie.",
        ),
        (
            "https://webep1.com/go/4ea3bd70c3",
            "Jaskółki",
            "Sprawdź smukłe jaskółki do łowienia ostrożnych drapieżników.",
        ),
        (
            "https://webep1.com/go/74ac1044c3",
            "Żyłki",
            "Porównaj żyłki pod średnicę, rozciągliwość i planowaną metodę.",
        ),
        (
            "https://webep1.com/go/c70fbfc0c3",
            "Fluorocarbon i mono",
            "Dobierz fluorocarbon lub przypon mono do przejrzystości wody i rodzaju zestawu.",
        ),
        (
            "https://webep1.com/go/d8ad8b8dc3",
            "Haczyki, kotwiczki i główki jigowe",
            "Uzupełnij zestaw o haki, kotwiczki i główki jigowe do wybranej techniki.",
        ),
        (
            "https://webep1.com/go/8877c7e5c3",
            "Agrafki i krętliki",
            "Sprawdź agrafki, krętliki i kółka łącznikowe do szybkiej zmiany zestawu.",
        ),
        (
            "https://webep1.com/go/663edc47c3",
            "Podbieraki i osęki",
            "Wybierz podbierak lub osękę, które ułatwią bezpieczne podebranie ryby.",
        ),
        (
            "https://webep1.com/go/6608d83bc3",
            "Wagi, miarki i chwytaki",
            "Zobacz narzędzia do ważenia, mierzenia i bezpiecznego przytrzymania ryby.",
        ),
        (
            "https://webep1.com/go/b1df355ec3",
            "Pudełka i skrzynki",
            "Uporządkuj przynęty i drobne akcesoria w pudełkach oraz skrzynkach.",
        ),
        (
            "https://webep1.com/go/59f24cf1c3",
            "Krzesełka i fotele wędkarskie",
            "Wybierz wygodne siedzisko na dłuższe zasiadki i wyprawy nad wodę.",
        ),
        (
            "https://webep1.com/go/3b181da2c3",
            "Torby wędkarskie",
            "Sprawdź torby do przenoszenia przynęt, akcesoriów i podstawowego wyposażenia.",
        ),
        (
            "https://webep1.com/go/371f5146c3",
            "Plecaki wędkarskie",
            "Porównaj plecaki na mobilne wyprawy, gdy cały sprzęt musi być pod ręką.",
        ),
        (
            "https://webep1.com/go/3f03d6c5c3",
            "Sprzęt elektroniczny",
            "Zobacz elektronikę wędkarską, która pomaga lepiej czytać wodę i planować wyprawę.",
        ),
    ),
}
def build_affiliate_links(rel):
    """Buduje jawny blok linków afiliacyjnych tylko dla skonfigurowanej strony."""
    items = AFFILIATE_LINKS.get(rel)
    if not items:
        return ""
    cards = "".join(
        f'<a class="affiliate-card" href="{html.escape(url, quote=True)}" '
        f'rel="sponsored noopener" target="_blank">'
        f'<strong>{html.escape(label)}</strong>'
        f'<span>{html.escape(description)}</span>'
        f'<span class="affiliate-card-cta">Sprawdź w BigRiver →</span></a>'
        for url, label, description in items
    )
    if rel == "zakupy.html":
        eyebrow = "Zakupy ze wsparciem"
        heading = "Sprzęt na kolejną wyprawę"
        intro = (
            "Zebraliśmy w jednym miejscu kategorie sprzętu, które pomagają skompletować "
            "zestaw na różne metody łowienia. To linki afiliacyjne — kupując z linku, "
            "wspierasz naszą stronę, a cena dla Ciebie się nie zmienia."
        )
    else:
        eyebrow = "Sprzęt do metody"
        heading = "Kompletuj feeder krok po kroku"
        intro = (
            "Jeśli chcesz porównać dostępne kategorie sprzętu, zacznij od tych czterech "
            "elementów. To linki afiliacyjne — FishPoint może otrzymać prowizję, "
            "ale cena dla Ciebie się nie zmienia."
        )
    return (
        f'{AFFILIATE_BEGIN}<section id="afiliacja" class="affiliate-section" '
        f'aria-label="Polecane kategorie sprzętu">'
        f'<p class="eyebrow">{eyebrow}</p>'
        f'<h2>{heading}</h2>'
        f'<p>{intro}</p>'
        f'<div class="affiliate-grid">{cards}</div>'
        f'</section>{AFFILIATE_END}'
    )


def _existing_internal_link(href):
    """Akceptuje wyłącznie ścieżkę do istniejącej strony statycznej."""
    if not href.startswith("/") or href.startswith("//"):
        return False
    rel = href.lstrip("/") or "index.html"
    if rel.endswith("/"):
        rel += "index.html"
    return os.path.isfile(os.path.join(ROOT, rel))


def _advantage_links(items):
    links = [
        f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
        for href, label in items if _existing_internal_link(href)
    ]
    return " · ".join(links)


def build_content_advantage(rel, config):
    """Buduje jawnie oznaczony, semantyczny blok odpowiedzi z konfiguracji strony."""
    table_title, headers, rows = config["table"]
    table_class = "starter-kit" if "pierwszy-zestaw" in rel else "decision-table"
    table_html = (
        f'<section class="{table_class}" aria-label="{html.escape(table_title)}">'
        f'<h2>{html.escape(table_title)}</h2><table class="{table_class}"><thead><tr>'
        + "".join(f"<th>{html.escape(cell)}</th>" for cell in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
            for row in rows
        )
        + "</tbody></table></section>"
    )
    mistakes = "".join(f"<li>{html.escape(item)}</li>" for item in config["mistakes"])
    spot = config.get("spot")
    spot_html = ""
    if spot:
        spot_title, spot_items = spot
        spot_html = (
            f'<h2>{html.escape(spot_title)}</h2><div class="spot-guide">'
            + "".join(f"<div><p>{html.escape(item)}</p></div>" for item in spot_items)
            + "</div>"
        )
    links = _advantage_links(config["links"])
    next_step = (
        f'<section class="article-next-step" aria-label="Następny krok">'
        f'<p><strong>Następny krok:</strong> {links}</p></section>'
        if links else ""
    )
    return (
        f'{CONTENT_ADVANTAGE_BEGIN}<section class="info-block content-advantage" '
        f'aria-label="Praktyczny skrót">'
        f'<section class="answer-first" aria-label="Najkrótsza odpowiedź">'
        f'<h2>Najkrótsza odpowiedź</h2><p>{html.escape(config["answer"])}</p></section>'
        f'{table_html}<h2>Typowe błędy początkujących</h2>'
        f'<ul class="beginner-mistakes">{mistakes}</ul>'
        f'{spot_html}<section class="methodology" aria-label="Metodologia">'
        f'<h2>Jak korzystać z poradnika</h2>'
        f'<p>{html.escape(config["method"])}</p></section>'
        f'<section class="source-list" aria-label="Źródła i weryfikacja">'
        f'<h2>Sprawdź źródło</h2><p>{html.escape(config["source_prompt"])}</p></section>'
        f'{next_step}</section>{CONTENT_ADVANTAGE_END}'
    )


def inject_content_advantage(src, rel):
    """Wstawia moduł w miejscu pasującym do typu strony."""
    config = CONTENT_ADVANTAGES.get(rel)
    if not config:
        return src
    block = build_content_advantage(rel, config)
    if rel in ("index.html", "pierwsze-kroki/index.html"):
        return re.sub(r'(<section class="section\b[^>]*>)', block + r"\1", src, count=1)
    if FISHPOINT_METHOD_END in src:
        return src.replace(FISHPOINT_METHOD_END, FISHPOINT_METHOD_END + block, 1)
    if TLDR_END in src:
        return src.replace(TLDR_END, TLDR_END + block, 1)
    if BYLINE_END in src:
        return src.replace(BYLINE_END, BYLINE_END + block, 1)
    return re.sub(r"(</h1>)", r"\1" + block, src, count=1)

# Powiązania są budowane z istniejących, redakcyjnie dobranych linków modułów
# content-advantage. Każdy artykuł prowadzi też do własnego hubu sekcji.
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


def build_related(section, rel, url):
    """Hub sekcji oraz maksymalnie trzy redakcyjnie wybrane strony-spokes."""
    related = [(BASE + f"/{section}/", f"Przegląd: {SECTIONS[section]}")]
    config = CONTENT_ADVANTAGES.get(rel, {})
    for href, title in config.get("links", ()):
        target = BASE + href
        if target != url and target not in {item[0] for item in related}:
            related.append((target, title))
        if len(related) == 4:
            break
    return related


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
    """Zamienia src obrazka (relatywny do strony) na ścieżkę od korzenia serwisu."""
    if src.startswith("http"):
        return src
    # Ścieżki zaczynające się od / są już ścieżkami publicznymi serwisu.
    # Nie wolno traktować ich jak ścieżek systemu plików (np. /assets -> /assets).
    if src.startswith("/"):
        return src
    abs_fs = os.path.normpath(os.path.join(page_dir, src))
    try:
        inside_root = os.path.commonpath((ROOT, abs_fs)) == ROOT
    except ValueError:
        inside_root = False
    if not inside_root:
        # Odporność na stare, błędnie nadmiarowe ../ w wygenerowanych stronach.
        clean = src
        while clean.startswith("../"):
            clean = clean[3:]
        candidate = os.path.normpath(os.path.join(ROOT, clean))
        if os.path.isfile(candidate):
            abs_fs = candidate
        else:
            return DEFAULT_IMG
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
    src, pubdate, mtime = ensure_content_meta(src, path)
    # Nie powielaj identycznego podpisu, jeśli redakcyjna edycja dodała go
    # obok automatycznego bloku byline.
    src = re.sub(
        r'(?P<meta><p class="article-meta">.*?</p>)\s*(?P=meta)',
        r'\g<meta>',
        src,
        count=1,
        flags=re.S,
    )
    noindex = is_noindex(src)
    # Każda strona ma jeden robots meta, odtwarzany w bloku seo:auto poniżej.
    src = robots_meta_re.sub("", src)
    # Wspólna nawigacja na każdej stronie — podmień istniejący nagłówek na
    # kanoniczny (z rozwijanymi działami). Prefiks ścieżek wg głębokości strony.
    depth = os.path.relpath(path, ROOT).replace(os.sep, "/").count("/")
    src = nav_re.sub(lambda m: build_nav("../" * depth), src, count=1)
    src = canonicalize_internal_hrefs(src)
    src = css_ver_re.sub(f'css/style.css?v={CSS_VER}"', src)
    # usuń poprzednie wstrzyknięcia, by działać idempotentnie
    src = block_re.sub("", src)
    src = byline_re.sub("", src)
    src = toc_re.sub("", src)
    src = tldr_re.sub("", src)
    src = related_re.sub("", src)
    src = newsletter_re.sub("", src)
    src = giscus_re.sub("", src)
    src = fishpoint_method_re.sub("", src)
    src = content_advantage_re.sub("", src)
    src = affiliate_re.sub("", src)
    src = replace_youtube_nocookie_embeds(src)
    # Pierwsze zdjęcie artykułu jest elementem LCP — nie odkładaj jego pobrania
    # mimo lazy-loadingu odziedziczonego po starszych szablonach.
    src = re.sub(
        r'(<img\b(?=[^>]*class="article-image")(?=[^>]*loading="lazy")[^>]*?)\sloading="lazy"',
        r'\1 loading="eager" fetchpriority="high"',
        src,
        count=1,
    )

    tm = title_re.search(src)
    dm = desc_re.search(src)
    if not tm or not dm:
        return None
    title_raw = tm.group(1).strip()
    desc_raw = dm.group(1).strip()
    title_txt = html.unescape(title_raw)
    desc_txt = html.unescape(desc_raw)

    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    # Ujednolic sezonowa etykiete w hero: publikacja w lipcu nie udaje wrzesniowej daty.
    src = src.replace("wrzesień 2026", "sezon jesienny 2026")
    url = BASE + rel_url(path)

    # obrazek OG: pierwszy <img> w treści, inaczej domyślny
    page_dir = os.path.dirname(path)
    im = img_re.search(src)
    img_path = resolve_img(im.group(1), page_dir) if im else DEFAULT_IMG
    # Strony narzędzi budują <img> w JS (brak statycznego) — nadaj sensowny OG
    TOOL_IMG = {
        "narzedzia/okresy-ochronne.html": "/assets/img/tematy/wedki.jpg",
        "narzedzia/stany-wod.html": "/assets/img/tematy/pogoda.jpg",
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

    # Daty pochodzą z trwałego komentarza content-meta, nie z mtime przebudowy.

    # --- OpenGraph + Twitter ---
    og_type = "website" if (is_home or is_section_index) else "article"

    # --- Widoczny podpis autora + daty (E-E-A-T, świeżość) na artykułach ---
    # Wstrzykiwany po pierwszym </h1>; pomijamy strony autora, słownik i przepisy.
    if og_type == "article" and rel not in ("o-autorze.html",):
        # Ręczne podpisy są zastępowane jednym blokiem automatycznym.
        src = re.sub(r'<p class="article-meta">.*?</p>', "", src, flags=re.S)
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
        src = inject_fishpoint_method(src, rel)
        # Hub sekcji i ręcznie wybrane powiązania z istniejących kart redakcyjnych.
        if section:
            rel_items = build_related(section, rel, url)
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
    src = inject_content_advantage(src, rel)
    src = re.sub(r"(</article>)", build_affiliate_links(rel) + r"\1", src, count=1)
    # Wstrzyknięte bloki też mogą zawierać stare odnośniki do index.html.
    src = canonicalize_internal_hrefs(src)
    head = [
        BEGIN,
        f'  <link rel="canonical" href="{url}" />',
        ('  <meta name="robots" content="noindex, follow" />'
         if noindex else
         '  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />'),
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
                return (new_src, url, mtime, is_home or is_section_index,
                        title_txt, desc_txt, page_images, noindex)
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
    return (new_src, url, mtime, is_home or is_section_index,
            title_txt, desc_txt, page_images, noindex)



def validate_generated_artifacts():
    """Deterministyczna kontrola metadanych i artefaktów publikacyjnych."""
    html_paths = []
    for dirpath, _, files in os.walk(ROOT):
        if "/.git" not in dirpath:
            html_paths.extend(
                os.path.join(dirpath, fn) for fn in files if fn.endswith(".html"))

    noindex_urls = set()
    for path in sorted(html_paths):
        with open(path, encoding="utf-8") as f:
            src = f.read()
        parse_content_meta(src, path)
        robots = robots_meta_re.findall(src)
        if len(robots) != 1:
            raise ValueError(f"{path}: oczekiwano dokładnie jednego meta robots")
        noindex = is_noindex(src)
        if noindex and not re.search(r'\bnoindex\s*,\s*follow\b', robots[0], re.I):
            raise ValueError(f"{path}: noindex musi jawnie zawierać follow")
        if os.path.basename(path) != "404.html":
            canonical = f'<link rel="canonical" href="{BASE + rel_url(path)}" />'
            if canonical not in src:
                raise ValueError(f"{path}: niekanoniczny lub brakujący canonical")
        if noindex:
            noindex_urls.add(BASE + rel_url(path))

    artifacts = ("sitemap.xml", "llms.txt", "llms-full.txt", "feed.xml")
    contents = {}
    for artifact in artifacts:
        with open(os.path.join(ROOT, artifact), encoding="utf-8") as f:
            contents[artifact] = f.read()
    for url in noindex_urls:
        for artifact, content in contents.items():
            if url in content:
                raise ValueError(f"{artifact}: zawiera noindex URL {url}")
    import xml.etree.ElementTree as ET
    ET.fromstring(contents["sitemap.xml"])
    ET.fromstring(contents["feed.xml"])
    print(f"Walidacja artefaktów: ok ({len(html_paths)} stron)")


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
            page_src = f.read()
        if is_noindex(page_src):
            continue
        tm = title_re.search(page_src)
        if not tm:
            continue
        SECTION_PAGES.setdefault(parts[0], []).append(
            (BASE + rel_url(p), short_title(html.unescape(tm.group(1).strip()))))

    # 404 jest pomijane w pętli (ścieżki absolutne), ale też ma mieć wspólne menu.
    p404 = os.path.join(ROOT, "404.html")
    if os.path.exists(p404):
        with open(p404, encoding="utf-8") as f:
            s404 = f.read()
        s404, _published, _modified = ensure_content_meta(s404, p404)
        s404 = robots_meta_re.sub("", s404)
        s404 = CONTENT_META_RE.sub(
            lambda match: match.group(0) + '\n  <meta name="robots" content="noindex, follow" />',
            s404,
            count=1,
        )
        s404 = nav_re.sub(lambda m: build_nav("/"), s404, count=1)
        s404 = canonicalize_internal_hrefs(s404)
        s404 = css_ver_re.sub(f'css/style.css?v={CSS_VER}"', s404)
        with open(p404, "w", encoding="utf-8") as f:
            f.write(s404)

    urls = []
    changed = 0
    for p in pages:
        res = build(p)
        if not res:
            print("POMINIĘTO (brak title/desc):", p)
            continue
        new_src, url, mtime, is_index, title_txt, desc_txt, page_images, noindex = res
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_src)
        if not noindex:
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
        if is_noindex(s):
            continue
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
    if sys.argv[1:] == ["--validate"]:
        validate_generated_artifacts()
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("użycie: seo_inject.py [--validate]")
