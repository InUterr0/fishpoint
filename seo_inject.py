#!/usr/bin/env python3
"""Wstrzykuje meta SEO (canonical, OpenGraph, Twitter, JSON-LD) do wszystkich
stron HTML oraz generuje sitemap.xml i robots.txt.

Idempotentny: blok SEO jest oznaczony znacznikami i przy ponownym uruchomieniu
zostaje podmieniony, a nie zdublowany. Wystarczy zmienić BASE po kupnie domeny
i uruchomić ponownie: python3 seo_inject.py
"""
import os, re, html, json, datetime, subprocess, functools, hashlib, sys, math, unicodedata
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://fish-point.pl"          # <-- PODMIEŃ po kupnie domeny i uruchom ponownie
# Komentarze giscus (GitHub Discussions) — na wpisach blogowych (aktualnosci).
# Puste GISCUS_REPO = wyłączone. Wymaga zainstalowania aplikacji giscus na repo.
GISCUS_REPO = "kerlingruppen/fishpoint-comments"
GISCUS_REPO_ID = "R_kgDOTTiC_g"
GISCUS_CATEGORY = "Announcements"
GISCUS_CATEGORY_ID = "DIC_kwDOTTiC_s4DA1zO"
# Newsletter — własny formularz wysyłający na endpoint MailerLite.
# Puste = sekcja newslettera się nie pojawia. Świadomie NIE używamy gotowej
# wklejki z panelu: ciągnęłaby ~15 kB własnego CSS, webfont Open Sans, dwa
# skrypty z obcych domen i pixel śledzący na każdy z 50 wpisów. Tu zostaje
# samo POST-owanie do ich API, a wygląd bierze się z .nl-form w style.css.
# Odpowiedź ląduje w ukrytej ramce, żeby wysłanie nie wyrzucało z artykułu.
NEWSLETTER_ACTION = ("https://assets.mailerlite.com/jsonp/2551268"
                     "/forms/194705373347710070/subscribe")
NEWSLETTER_EMBED = (
    f'<form class="nl-form" action="{NEWSLETTER_ACTION}" method="post"'
    ' target="nl-sink" data-newsletter>'
    '<input type="email" name="fields[email]" required autocomplete="email"'
    ' aria-label="Twój adres e-mail" placeholder="Twój adres e-mail" />'
    '<input type="hidden" name="ml-submit" value="1" />'
    '<input type="hidden" name="anticsrf" value="true" />'
    '<button type="submit">Zapisz się</button>'
    '</form>'
    '<iframe name="nl-sink" title="Zapis do newslettera" hidden></iframe>'
    '<p class="nl-msg nl-msg--ok" hidden>Prawie gotowe — sprawdź skrzynkę'
    ' i kliknij link potwierdzający zapis.</p>'
    '<p class="nl-note">Newsletter obsługuje MailerLite. Wypiszesz się'
    ' jednym kliknięciem w każdej wiadomości.</p>'
    '<script>document.currentScript.previousElementSibling'
    '.parentNode.querySelector("[data-newsletter]")'
    '.addEventListener("submit",function(e){'
    'var s=e.target.parentNode.querySelector(".nl-msg");'
    'e.target.hidden=true;s.hidden=false;});</script>'
)
SITE_NAME = "FishPoint"
AUTHOR_NAME = "Maciej Baniewicz"
DEFAULT_IMG = "/assets/img/tematy/wedki.jpg"
TOOL_IMG = {
    "aktualnosci/gorne-wymiary-ochronne-2026.html": "/assets/img/tematy/kalendarz.jpg",
    "aktualnosci/kalendarz-wedkarski-2026.html": "/assets/img/tematy/kalendarz.jpg",
    "aktualnosci/kiedy-sezon-na-ryby-2026.html": "/assets/img/tematy/kalendarz.jpg",
    "aktualnosci/mistrzostwa-polski-splawik-swierkocin-2026.html": "/assets/img/tematy/splawik.jpg",
    "aktualnosci/pierwsze-okregowe-method-feeder-opole-2026.html": "/assets/img/tematy/wedki.jpg",
    "aktualnosci/przeglad-nowosci-sezonu.html": "/assets/img/aktualnosci/przeglad-nowosci-sezonu.jpg",
    "aktualnosci/wymiary-i-okresy-ochronne-2026.html": "/assets/img/tematy/kalendarz.jpg",
    "aktualnosci/zezwolenia-online-2026.html": "/assets/img/tematy/wedki.jpg",
    "aktualnosci/wytyczne-wody-polskie-obwody-rybackie-2026.html": "/assets/img/tematy/jeziora.jpg",
    "aktualnosci/zakaz-polowu-bobr-lipiec-2026.html": "/assets/img/tematy/muchowe.jpg",
    "aktualnosci/zawody-wedkarskie-2026-kalendarz.html": "/assets/img/tematy/kalendarz.jpg",
    "poradniki/co-lowic-w-styczniu.html": "/assets/img/tematy/pogoda.jpg",
    "poradniki/co-lowic-w-lutym.html": "/assets/img/tematy/kolowrotki.jpg",
    "poradniki/co-lowic-w-marcu.html": "/assets/img/tematy/stawy.jpg",
    "poradniki/co-lowic-w-kwietniu.html": "/assets/img/tematy/splawik.jpg",
    "poradniki/co-lowic-w-maju.html": "/assets/img/tematy/jeziora.jpg",
    "poradniki/co-lowic-w-czerwcu.html": "/assets/img/tematy/akcesoria.jpg",
    "poradniki/co-lowic-w-lipcu.html": "/assets/img/tematy/cr.jpg",
    "poradniki/co-lowic-w-sierpniu.html": "/assets/img/tematy/wedki.jpg",
    "poradniki/co-lowic-w-wrzesniu.html": "/assets/img/tematy/muchowe.jpg",
    "poradniki/co-lowic-w-pazdzierniku.html": "/assets/img/tematy/kalendarz.jpg",
    "poradniki/co-lowic-w-listopadzie.html": "/assets/img/tematy/wezly.jpg",
    "poradniki/co-lowic-w-grudniu.html": "/assets/img/tematy/pogoda.jpg",
    "poradniki/echosondy.html": "/assets/img/tematy/wedki.jpg",
    "poradniki/etyka-i-przepisy.html": "/assets/img/tematy/cr.jpg",
    "poradniki/wedkarstwo-z-lodzi.html": "/assets/img/tematy/jeziora.jpg",
    "poradniki/zanety-domowe.html": "/assets/img/tematy/akcesoria.jpg",
    "techniki/trolling.html": "/assets/img/ryby/szczupak.jpg",
    "narzedzia/czy-moge-zabrac-rybe.html": "/assets/img/tematy/kalendarz.jpg",
    "narzedzia/dobor-sprzetu.html": "/assets/img/tematy/wedki.jpg",
    "narzedzia/kalendarz-bran.html": "/assets/img/tematy/kalendarz.jpg",
    "narzedzia/kalendarz-ksiezycowy.html": "/assets/img/tematy/kalendarz.jpg",
    "narzedzia/kalkulator-wagi-ryby.html": "/assets/img/ryby/karp.jpg",
    "narzedzia/okresy-ochronne.html": "/assets/img/tematy/wedki.jpg",
    "narzedzia/prognoza-bran.html": "/assets/img/tematy/kalendarz.jpg",
    "narzedzia/rozpoznaj-rybe.html": "/assets/img/ryby/okon.jpg",
    "narzedzia/stany-wod.html": "/assets/img/tematy/pogoda.jpg",
    "narzedzia/index.html": "/assets/img/tematy/wedki.jpg",
    "pierwsze-kroki/twoj-pierwszy-wyjazd-na-ryby.html": "/assets/img/tematy/kalendarz.jpg",
    "pierwsze-kroki/pierwszy-zestaw-wedkarski-budzet.html": "/assets/img/tematy/wedki.jpg",
    "pierwsze-kroki/jak-nabic-przynete-i-odhaczyc-rybe.html": "/assets/img/tematy/wezly.jpg",
    "sprzet/pierwsza-wedka-spinningowa.html": "/assets/img/tematy/wedka-spinningowa-zestaw.jpg",
    # Kalendarze brań domyślnie biorą obraz gatunku z Wikimedia; te dwa mają
    # własne zdjęcie z połowu, więc wskazujemy je wprost.
    "poradniki/kalendarz-bran-szczupak.html": "/assets/img/ryby/szczupak-las.jpg",
    "poradniki/kalendarz-bran-leszcz.html": "/assets/img/ryby/leszcz-noc.jpg",
    "zgodnie-z-zasadami.html": "/assets/img/tematy/cr.jpg",
    "humor/dowcipy.html": "/assets/img/humor/dowcipy.jpg",
    "humor/memy.html": "/assets/img/humor/memy.jpg",
    "lowiska/dolnoslaskie.html": "/assets/img/tematy/jeziora.jpg",
    "lowiska/kujawsko-pomorskie.html": "/assets/img/tematy/stawy.jpg",
    "lowiska/lodzkie.html": "/assets/img/tematy/muchowe.jpg",
    "lowiska/lubelskie.html": "/assets/img/tematy/pogoda.jpg",
    "lowiska/lubuskie.html": "/assets/img/tematy/kalendarz.jpg",
    "lowiska/malopolskie.html": "/assets/img/tematy/splawik.jpg",
    "lowiska/mazowieckie.html": "/assets/img/tematy/wedki.jpg",
    "lowiska/opolskie.html": "/assets/img/tematy/cr.jpg",
    "lowiska/podkarpackie.html": "/assets/img/tematy/jeziora.jpg",
    "lowiska/podlaskie.html": "/assets/img/tematy/stawy.jpg",
    "lowiska/pomorskie.html": "/assets/img/tematy/muchowe.jpg",
    "lowiska/slaskie.html": "/assets/img/tematy/pogoda.jpg",
    "lowiska/swietokrzyskie.html": "/assets/img/tematy/kalendarz.jpg",
    "lowiska/warminsko-mazurskie.html": "/assets/img/tematy/splawik.jpg",
    "lowiska/wielkopolskie.html": "/assets/img/tematy/wedki.jpg",
    "lowiska/zachodniopomorskie.html": "/assets/img/tematy/cr.jpg",
}
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
    "bolen": {"name": "Boleń pospolity", "sameAs": ["https://pl.wikipedia.org/wiki/Boleń_pospolity", "https://www.wikidata.org/wiki/Q25473019"]},
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
    "karas": {
        "name": "Karaś pospolity",
        "sameAs": ["https://pl.wikipedia.org/wiki/Karaś_pospolity", "https://www.wikidata.org/wiki/Q194031"],
        "additional": (
            {"name": "Karaś srebrzysty", "sameAs": ["https://pl.wikipedia.org/wiki/Karaś_srebrzysty", "https://www.wikidata.org/wiki/Q725983"]},
        ),
    },
    "troc-losos": {
        "name": "Troć wędrowna",
        "sameAs": ["https://pl.wikipedia.org/wiki/Troć_wędrowna", "https://www.wikidata.org/wiki/Q1095355"],
        "additional": (
            {"name": "Łosoś szlachetny", "sameAs": ["https://pl.wikipedia.org/wiki/Łosoś_szlachetny", "https://www.wikidata.org/wiki/Q188879"]},
        ),
    },
    "sielawa": {"name": "Sielawa", "sameAs": ["https://pl.wikipedia.org/wiki/Sielawa_europejska", "https://www.wikidata.org/wiki/Q754061"]},
    "sieja": {"name": "Sieja", "sameAs": ["https://www.wikidata.org/wiki/Q1034400", "https://www.fishbase.se/summary/48236"]},
    "brzana": {"name": "Brzana pospolita", "sameAs": ["https://pl.wikipedia.org/wiki/Brzana_pospolita", "https://www.wikidata.org/wiki/Q326219"]},
    "certa": {"name": "Certa", "sameAs": ["https://pl.wikipedia.org/wiki/Certa", "https://www.wikidata.org/wiki/Q247370"]},
    "swinka": {"name": "Świnka pospolita", "sameAs": ["https://pl.wikipedia.org/wiki/Świnka_pospolita", "https://www.wikidata.org/wiki/Q654583"]},
    "wzdrega": {"name": "Wzdręga", "sameAs": ["https://pl.wikipedia.org/wiki/Wzdręga", "https://www.wikidata.org/wiki/Q200594"]},
    "ukleja": {"name": "Ukleja pospolita", "sameAs": ["https://pl.wikipedia.org/wiki/Ukleja_pospolita", "https://www.wikidata.org/wiki/Q200473"]},
    "jesiotr": {"name": "Jesiotr ostronosy", "sameAs": ["https://pl.wikipedia.org/wiki/Jesiotr_ostronosy", "https://www.wikidata.org/wiki/Q756969"]},
    "dorsz": {"name": "Dorsz atlantycki", "sameAs": ["https://pl.wikipedia.org/wiki/Dorsz_atlantycki", "https://www.wikidata.org/wiki/Q199788"]},
    "sledz": {"name": "Śledź atlantycki", "sameAs": ["https://pl.wikipedia.org/wiki/Śledź_oceaniczny", "https://www.wikidata.org/wiki/Q2396858"]},
    "belona": {"name": "Belona", "sameAs": ["https://pl.wikipedia.org/wiki/Belona_(ryba)", "https://www.wikidata.org/wiki/Q643373"]},
    "fladra": {"name": "Flądra (stornia)", "sameAs": ["https://pl.wikipedia.org/wiki/Stornia", "https://www.wikidata.org/wiki/Q214034"]},
    "kielb": {"name": "Kiełb pospolity", "sameAs": ["https://www.fishbase.se/summary/Gobio-gobio.html"]},
    "krap": {"name": "Krąp", "sameAs": ["https://www.fishbase.se/summary/Blicca-bjoerkna.html"]},
    "koza": {"name": "Koza pospolita", "sameAs": ["https://www.fishbase.se/summary/Cobitis-taenia.html"]},
    "piskorz": {"name": "Piskorz", "sameAs": ["https://www.fishbase.se/summary/Misgurnus-fossilis.html"]},
    "rozanka": {"name": "Różanka", "sameAs": ["https://www.fishbase.se/summary/Rhodeus-amarus.html"]},
    "ciernik": {"name": "Ciernik", "sameAs": ["https://www.fishbase.se/summary/Gasterosteus-aculeatus.html"]},
    "slonecznica": {"name": "Słonecznica", "sameAs": ["https://www.fishbase.se/summary/Leucaspius-delineatus.html"]},
    "strzebla-potokowa": {"name": "Strzebla potokowa", "sameAs": ["https://www.fishbase.se/summary/Phoxinus-phoxinus.html"]},
    "glowacz-bialopletwy": {"name": "Głowacz białopłetwy", "sameAs": ["https://www.fishbase.se/summary/Cottus-gobio.html"]},
    "minog-rzeczny": {"name": "Minóg rzeczny", "sameAs": ["https://www.fishbase.se/summary/Lampetra-fluviatilis.html"]},
}

# Tematy metod i miejsc przypisujemy wyłącznie do stron, których widoczna treść
# jednoznacznie je opisuje. Brak wpisu jest celowy: generator nie zgaduje encji
# na podstawie pojedynczego słowa ani nazwy pliku.
METHOD_ENTITIES = {
    "techniki/spinning.html": "Spinning",
    "techniki/feeder.html": "Feeder",
    "techniki/splawik.html": "Wędkarstwo spławikowe",
    "techniki/karpiowanie.html": "Wędkarstwo karpiowe",
    "techniki/muchowe.html": "Wędkarstwo muchowe",
    "techniki/podlodowe.html": "Wędkarstwo podlodowe",
    "techniki/trolling.html": "Trolling",
    "aktualnosci/pierwsze-okregowe-method-feeder-opole-2026.html": "Method feeder",
    "aktualnosci/mistrzostwa-polski-splawik-swierkocin-2026.html": "Wędkarstwo spławikowe",
}
PLACE_ENTITIES = {
    "aktualnosci/zakaz-polowu-bobr-lipiec-2026.html": (
        {"@type": "RiverBodyOfWater", "name": "Bóbr",
         "sameAs": "https://www.wikidata.org/wiki/Q148307"},
    ),
    "aktualnosci/mistrzostwa-polski-splawik-swierkocin-2026.html": (
        {"@type": "RiverBodyOfWater", "name": "Warta",
         "sameAs": "https://www.wikidata.org/wiki/Q201823"},
        {"@type": "Place", "name": "Świerkocin",
         "sameAs": "https://www.wikidata.org/wiki/Q3078474"},
    ),
    "aktualnosci/troc-jeziorowa-85-kg-tarnobrzeg-2026.html": (
        {"@type": "LakeBodyOfWater", "name": "Jezioro Tarnobrzeskie",
         "sameAs": "https://www.wikidata.org/wiki/Q6477976"},
    ),
}

# Rejestr biologiczny atlasu. Tożsamość taksonomiczną oddzielamy od porad
# praktycznych i od lokalnych przepisów: zewnętrzne bazy opisują gatunek, nie
# potwierdzają obecności na konkretnej wodzie ani legalności połowu.
BIOLOGICAL_SOURCE_DATE = "2026-07-17"
BIOLOGICAL_SOURCE_SCOPE = (
    "tożsamość taksonomiczna i nazewnictwo oraz, gdy wskazano, ocena ochrony; "
    "bez potwierdzenia lokalnego występowania, stanu łowiska ani zasad połowu"
)
FISH_BIOLOGICAL_REGISTRY = {
    "szczupak": {
        "latin": "Esox lucius", "group": "drapieżniki", "aliases": ("szczupak pospolity",), "compare": "sandacz",
        "biological_sources": (
            ("https://doi.org/10.5878/mjhw-wp21", "SLU: dane i kod badania (2025)",
             "dynamika populacji, odłowy i przemieszczanie szczupaka w tarlisku Bałtyku (2017–2022); nie opisuje wszystkich wód"),
            ("https://www.fishbase.se/summary/Esox_lucius.html", "FishBase: Esox lucius",
             "tożsamość taksonomiczna i opis gatunku; nie potwierdza lokalnego występowania ani zasad połowu"),
        ),
    },
    "sandacz": {"latin": "Sander lucioperca", "group": "drapieżniki", "aliases": ("zander",), "compare": "okon"},
    "okon": {"latin": "Perca fluviatilis", "group": "drapieżniki", "aliases": ("perch",), "compare": "sandacz"},
    "sum": {"latin": "Silurus glanis", "group": "drapieżniki", "aliases": ("sum europejski",), "compare": "szczupak"},
    "bolen": {"latin": "Leuciscus aspius", "group": "drapieżniki", "aliases": ("asp",), "compare": "ukleja"},
    "wegorz": {
        "latin": "Anguilla anguilla", "group": "drapieżniki", "aliases": ("węgorz europejski",), "compare": "mietus",
        "caution": "Porada ICES dotyczy całego naturalnego zasięgu i nie rozstrzyga legalności połowu na konkretnej wodzie.",
        "biological_sources": (
            ("https://asd.ices.dk/viewAdvice/4001",
             "ICES Advice: wydano 2025 r.; ocena 2025 r.; porada dla 2026 r. (ele.2737.nea)",
             "porada naukowa dla 2026 r. w całym naturalnym zasięgu węgorza europejskiego; nie jest lokalnym przepisem"),
            ("https://doi.org/10.17895/ices.advice.27203028", "DOI porady ICES: ele.2737.nea",
             "trwały identyfikator porady wydanej w 2025 r., odnoszącej się do oceny 2025 r. i okresu porady 2026 r."),
            ("https://sg.ices.dk/ViewCharts.aspx?key=21231", "ICES Stock Assessment Graphs",
             "dane i wykresy oceny zasobu ele.2737.nea (2025); skala całego naturalnego zasięgu"),
        ),
    },
    "karp": {"latin": "Cyprinus carpio", "group": "spokojny żer", "aliases": ("karp europejski",), "compare": "amur"},
    "lin": {"latin": "Tinca tinca", "group": "spokojny żer", "aliases": ("tench",), "compare": "karas"},
    "leszcz": {"latin": "Abramis brama", "group": "spokojny żer", "aliases": ("bream",), "compare": "ploc"},
    "jaz": {"latin": "Leuciscus idus", "group": "spokojny żer", "aliases": ("ide",), "compare": "klen"},
    "pstrag": {"latin": "Salmo trutta", "group": "łososiowate i inne", "aliases": ("pstrąg potokowy",), "compare": "lipien"},
    "mietus": {"latin": "Lota lota", "group": "łososiowate i inne", "aliases": ("burbot",), "compare": "wegorz"},
    "lipien": {"latin": "Thymallus thymallus", "group": "łososiowate i inne", "aliases": ("grayling",), "compare": "pstrag"},
    "ploc": {"latin": "Rutilus rutilus", "group": "spokojny żer", "aliases": ("roach",), "compare": "wzdrega"},
    "klen": {"latin": "Squalius cephalus", "group": "spokojny żer", "aliases": ("chub",), "compare": "jaz"},
    "amur": {"latin": "Ctenopharyngodon idella", "group": "spokojny żer", "aliases": ("amur biały", "grass carp"), "compare": "karp",
             "caution": "Informacja o introdukcji nie potwierdza samodzielnego rozmnażania ani obecności populacji na wybranej wodzie."},
    "karas": {"latin": "Carassius carassius", "taxa": ("Carassius carassius", "Carassius gibelio"), "group": "spokojny żer",
              "aliases": ("karaś pospolity", "karaś srebrzysty"), "compare": "lin"},
    "troc-losos": {"latin": "Salmo trutta", "taxa": ("Salmo trutta", "Salmo salar"), "group": "łososiowate i inne",
                    "aliases": ("troć wędrowna", "łosoś szlachetny"), "compare": "sielawa"},
    "sielawa": {"latin": "Coregonus albula", "group": "łososiowate i inne", "aliases": ("vendace",), "compare": "sieja"},
    "sieja": {"latin": "Coregonus maraena", "group": "łososiowate i inne", "aliases": ("sieja europejska", "maraena whitefish"), "compare": "sielawa"},
    "brzana": {"latin": "Barbus barbus", "group": "spokojny żer", "aliases": ("barbel",), "compare": "swinka",
                "caution": "Nie traktuj wzmianki o ikrze jako porady kulinarnej: nie spożywaj jej bez wiarygodnej identyfikacji i informacji bezpieczeństwa."},
    "certa": {"latin": "Vimba vimba", "group": "spokojny żer", "aliases": ("vimba",), "compare": "swinka"},
    "swinka": {"latin": "Chondrostoma nasus", "group": "łososiowate i inne", "aliases": ("nase",), "compare": "brzana"},
    "wzdrega": {"latin": "Scardinius erythrophthalmus", "group": "spokojny żer", "aliases": ("rudd",), "compare": "ploc"},
    "ukleja": {"latin": "Alburnus alburnus", "group": "spokojny żer", "aliases": ("bleak",), "compare": "bolen"},
    "jesiotr": {"latin": "Acipenser oxyrinchus", "group": "łososiowate i inne", "aliases": ("jesiotr ostronosy",), "compare": "dorsz"},
    "dorsz": {"latin": "Gadus morhua", "group": "morskie", "aliases": ("dorsz atlantycki",), "compare": "sledz"},
    "sledz": {"latin": "Clupea harengus", "group": "morskie", "aliases": ("śledź atlantycki",), "compare": "belona"},
    "belona": {"latin": "Belone belone", "group": "morskie", "aliases": ("garfish",), "compare": "sledz",
               "caution": "Zielona barwa ości nie jest rozstrzygającą cechą rozpoznawczą ani oceną przydatności do spożycia."},
    "fladra": {"latin": "Platichthys flesus", "group": "morskie", "aliases": ("stornia", "flądra"), "compare": "dorsz"},
    "kielb": {"latin": "Gobio gobio", "group": "spokojny żer",
              "aliases": ("kiełb pospolity", "gudgeon"), "compare": "krap"},
    "krap": {"latin": "Blicca bjoerkna", "group": "spokojny żer",
             "aliases": ("krąpik", "silver bream"), "compare": "leszcz"},
    "koza": {"latin": "Cobitis taenia", "group": "łososiowate i inne",
             "aliases": ("koza pospolita", "spined loach"), "compare": "piskorz"},
    "piskorz": {"latin": "Misgurnus fossilis", "group": "łososiowate i inne",
                "aliases": ("piskorz europejski", "weather loach"), "compare": "koza"},
    "rozanka": {"latin": "Rhodeus amarus", "group": "łososiowate i inne",
                "aliases": ("różanka pospolita", "bitterling"), "compare": "slonecznica"},
    "ciernik": {"latin": "Gasterosteus aculeatus", "group": "spokojny żer",
                "aliases": ("ciernik pospolity", "three-spined stickleback"), "compare": "slonecznica"},
    "slonecznica": {"latin": "Leucaspius delineatus", "group": "łososiowate i inne",
                    "aliases": ("słonecznica pospolita", "sunbleak"), "compare": "ukleja"},
    "strzebla-potokowa": {"latin": "Phoxinus phoxinus", "group": "łososiowate i inne",
                          "aliases": ("strzebla", "common minnow"), "compare": "kielb"},
    "glowacz-bialopletwy": {"latin": "Cottus gobio", "group": "łososiowate i inne",
                            "aliases": ("głowacz", "European bullhead"), "compare": "pstrag"},
    "minog-rzeczny": {"latin": "Lampetra fluviatilis", "group": "łososiowate i inne",
                      "aliases": ("minog", "river lamprey"), "compare": "wegorz"},
}

# Tylko bezpośrednie karty gatunków potwierdzone w przeglądzie atlasu
# 2026-07-17. Brak wpisu oznacza, że nie emitujemy odnośnika IUCN.
FISH_BIOLOGICAL_REGISTRY_IUCN_URLS = {
    "amur": "https://www.iucnredlist.org/species/61295/3102796",
    "belona": "https://www.iucnredlist.org/species/198573/15536157",
    "bolen": "https://www.iucnredlist.org/species/2178/135082600",
    "brzana": "https://www.iucnredlist.org/species/2561/58293571",
    "certa": "https://www.iucnredlist.org/species/254508616/135094309",
    "dorsz": "https://www.iucnredlist.org/species/8784/12931575",
    "fladra": "https://www.iucnredlist.org/species/170759990/135112220",
    "jaz": "https://www.iucnredlist.org/species/11884/135089209",
    "karas": "https://www.iucnredlist.org/species/3849/58294635",
    "karp": "https://www.iucnredlist.org/species/6181/3107721",
    "klen": "https://www.iucnredlist.org/species/61205/135101356",
    "leszcz": "https://www.iucnredlist.org/species/135696/135068434",
    "lin": "https://www.iucnredlist.org/species/21912/2780110",
    "lipien": "https://www.iucnredlist.org/species/266178365/135093349",
    "mietus": "https://www.iucnredlist.org/species/135675/135110342",
    "okon": "https://www.iucnredlist.org/species/16580/58297645",
    "ploc": "https://www.iucnredlist.org/species/19787/58301083",
    "pstrag": "https://www.iucnredlist.org/species/19861/58301467",
    "sandacz": "https://www.iucnredlist.org/species/20860/58302439",
    "sieja": "https://www.iucnredlist.org/species/135672/84475793",
    "sielawa": "https://www.iucnredlist.org/species/242158594/242163476",
    "sledz": "https://www.iucnredlist.org/species/155123/4717767",
    "sum": "https://www.iucnredlist.org/species/40713/58305522",
    "swinka": "https://www.iucnredlist.org/species/225435143/135083986",
    "troc-losos": "https://www.iucnredlist.org/species/19861/58301467",
    "ukleja": "https://www.iucnredlist.org/species/789/135064432",
    "wzdrega": "https://www.iucnredlist.org/species/19946/58302044",
}
for _fish_slug, _iucn_url in FISH_BIOLOGICAL_REGISTRY_IUCN_URLS.items():
    FISH_BIOLOGICAL_REGISTRY[_fish_slug]["iucn_url"] = _iucn_url

# Krajowy skrót prawny do kart atlasu. Tekst celowo rozróżnia wody
# śródlądowe i morskie; zawsze prowadzi do aktu oraz zasad konkretnej wody.
FISH_LEGAL_SUMMARIES = {
    "szczupak": "Wody śródlądowe: wymiar 45 cm; okres ochronny 1 stycznia–30 kwietnia.",
    "sandacz": "Wody śródlądowe: wymiar 45 cm; okres ochronny 1 marca–31 maja.",
    "okon": "Wody śródlądowe: § 6–7 nie ustanawia krajowego wymiaru ani okresu; sprawdź zasady lokalne.",
    "sum": "Wody śródlądowe: wymiar 70 cm; okres ochronny 1 stycznia–31 maja.",
    "bolen": "Wody śródlądowe: wymiar 40 cm; § 7 nie ustanawia krajowego okresu ochronnego.",
    "wegorz": "Wody śródlądowe: wymiar 50 cm; okres ochronny 1 grudnia–31 marca.",
    "karp": "Wody śródlądowe: § 6–7 nie ustanawia krajowego wymiaru ani okresu; sprawdź zasady lokalne.",
    "lin": "Wody śródlądowe: wymiar 25 cm; § 7 nie ustanawia krajowego okresu ochronnego.",
    "leszcz": "Wody śródlądowe: § 6–7 nie ustanawia krajowego wymiaru ani okresu; sprawdź zasady lokalne.",
    "jaz": "Wody śródlądowe: wymiar 25 cm; § 7 nie ustanawia krajowego okresu ochronnego.",
    "pstrag": "Pstrąg potokowy: wymiar 25 albo 30 cm i okres 1 września–31 stycznia albo 31 grudnia, zależnie od wskazanego odcinka.",
    "mietus": "Wody śródlądowe: wymiar 25 albo 30 cm; okres 1 grudnia–koniec lutego, z wyjątkiem wskazanego odcinka Odry.",
    "lipien": "Wody śródlądowe: wymiar 30 cm; okres ochronny 1 marca–31 maja.",
    "ploc": "Wody śródlądowe: § 6–7 nie ustanawia krajowego wymiaru ani okresu; sprawdź zasady lokalne.",
    "klen": "Wody śródlądowe: wymiar 25 cm; § 7 nie ustanawia krajowego okresu ochronnego.",
    "amur": "Wody śródlądowe: § 6–7 nie ustanawia krajowego wymiaru ani okresu. Amur jest gatunkiem nierodzimym; § 8 nakazuje złowiony okaz niezwłocznie uśmiercić i zakazuje wpuszczenia go do jakiejkolwiek wody.",
    "karas": "Karaś pospolity: § 6–7 nie ustanawia krajowego wymiaru ani okresu. Karaś srebrzysty jest gatunkiem nierodzimym; § 8 nakazuje złowiony okaz niezwłocznie uśmiercić i zakazuje wpuszczenia go do jakiejkolwiek wody.",
    "troc-losos": "Troć i łosoś: wymiar 35 cm; okres i dodatkowe dni zakazu zależą od odcinka. Na morzu obowiązują odrębne przepisy GIRM.",
    "sielawa": "Wody śródlądowe: wymiar 18 cm; okres ochronny 15 października–31 grudnia.",
    "sieja": "Wody śródlądowe: wymiar 35 cm; okres ochronny 15 października–31 grudnia.",
    "brzana": "Wody śródlądowe: wymiar 40 cm; okres ochronny 1 stycznia–30 czerwca.",
    "certa": "Wymiar 30 cm; okres 1 września–30 listopada w Wiśle od zapory we Włocławku do ujścia, a 1 stycznia–30 czerwca w pozostałych wodach.",
    "swinka": "Wody śródlądowe: wymiar 25 cm; okres ochronny 1 stycznia–15 maja.",
    "wzdrega": "Wody śródlądowe: wymiar 15 cm; § 7 nie ustanawia krajowego okresu ochronnego.",
    "ukleja": "Wody śródlądowe: § 6–7 nie ustanawia krajowego wymiaru ani okresu; sprawdź zasady lokalne.",
    "jesiotr": "Jesiotr ostronosy: okres ochronny przez cały rok; nie traktuj tej karty jako wskazania celu połowu.",
    "dorsz": "Wody morskie: okres ochronny w rybołówstwie rekreacyjnym trwa cały rok; złowioną rybę niezwłocznie wypuść.",
    "sledz": "Wody morskie: sprawdź aktualne zasady, limity i komunikaty GIRM przed połowem.",
    "belona": "Wody morskie: sprawdź aktualne zasady, limity i komunikaty GIRM przed połowem.",
    "fladra": "Wody morskie: sprawdź aktualne zasady, limity i komunikaty GIRM przed połowem.",
}

FISH_LEGAL_SECTION_RE = re.compile(
    r'<section class="info-block(?: fish-legal-current)?"[^>]*><h3>'
    r'(?:Wymiar(?: ochronny)?|Status ochronny|Ograniczenia UE|Przepisy — połów morski|Przepisy krajowe i zasady lokalne)'
    r'.*?</h3><p>.*?</p></section>',
    re.S,
)


def build_fish_legal_section(slug, group):
    """Buduje jedyną kartę prawną atlasu z krajowym źródłem pierwotnym."""
    legal_summary = FISH_LEGAL_SUMMARIES[slug]
    inland_sections = "§ 6–8" if slug in {"amur", "karas"} else "§ 6–7"
    inland_source = (
        '<a href="https://eli.gov.pl/api/acts/DU/2023/1373/text.html" '
        f'rel="noopener external" target="_blank">Dz.U. 2023 poz. 1373, {inland_sections}</a>'
    )
    marine_source = (
        '<a href="https://www.gov.pl/web/girm/informacje-ogolne-nt-rybolowstwa-rekreacyjnego" '
        'rel="noopener external" target="_blank">aktualne informacje GIRM</a>'
    )
    if group == "morskie":
        legal_sources = marine_source
    elif slug == "troc-losos":
        legal_sources = inland_source + " · " + marine_source
    else:
        legal_sources = inland_source
    table_label = (
        "Otwórz tabelę i dobierz właściwy odcinek wody"
        if slug in {"pstrag", "mietus", "troc-losos", "certa"}
        else "Otwórz pełną tabelę okresów i wymiarów"
    )
    day_off_note = (
        '<p><strong>Granica okresu ochronnego:</strong> jeżeli pierwszy lub ostatni '
        'dzień okresu przypada w dzień ustawowo wolny od pracy, okres skraca się '
        'o ten dzień (§ 7 ust. 2); wyjątkiem jest całoroczna ochrona jesiotra.</p>'
        if group != "morskie" else ""
    )
    return (
        '<section class="info-block fish-legal-current" '
        'aria-label="Aktualne przepisy krajowe i zasady lokalne">'
        '<h3>Przepisy krajowe i zasady lokalne</h3>'
        f'<p><strong>Przepisy krajowe:</strong> {html.escape(legal_summary)} '
        f'<strong>Źródło:</strong> {legal_sources}</p>'
        f'{day_off_note}'
        '<p><strong>Przed połowem:</strong> sprawdź aktualny regulamin i zezwolenie '
        'dla konkretnej wody. Wymiar, okres, limit lub zakaz lokalny może być '
        'ostrzejszy; brak wartości krajowej nie oznacza zgody na zabranie ryby.</p>'
        f'<p><a href="../narzedzia/okresy-ochronne.html">{table_label}</a>.</p>'
        '</section>'
    )


# Konkurenci w SERP „kalendarz brań <gatunek>" trzymają rok w tytule, a GSC
# notuje zapytania z rokiem. Trzymamy go w jednej stałej: raz w roku zmienia
# się tutaj, a nie w kilkunastu plikach.
CALENDAR_TITLE_YEAR = "2026"
CALENDAR_TITLE_RE = re.compile(
    r"(<title>Kalendarz brań [^<]*?)(?:\s+20\d{2})?(\s*(?:—|\|)[^<]*</title>)"
)


def ensure_calendar_year(src, rel):
    """Utrzymuje aktualny rok w tytułach kalendarza brań per gatunek."""
    if not rel.startswith("poradniki/kalendarz-bran-"):
        return src
    return CALENDAR_TITLE_RE.sub(
        lambda match: f"{match.group(1)} {CALENDAR_TITLE_YEAR}{match.group(2)}",
        src,
        count=1,
    )


def normalize_fish_legal_section(src, rel):
    """Zastępuje starszy opis PZW jedną kartą opartą na aktualnym akcie."""
    if not rel.startswith("ryby/"):
        return src
    slug = os.path.splitext(os.path.basename(rel))[0]
    record = FISH_BIOLOGICAL_REGISTRY.get(slug)
    if not record or slug not in FISH_LEGAL_SUMMARIES:
        return src
    section = build_fish_legal_section(slug, record["group"])
    return FISH_LEGAL_SECTION_RE.sub(section, src, count=1)


CALENDAR_LEGAL_BEGIN = "<!--calendar-legal:auto-->"
CALENDAR_LEGAL_END = "<!--/calendar-legal:auto-->"
calendar_legal_re = re.compile(
    re.escape(CALENDAR_LEGAL_BEGIN) + r".*?" + re.escape(CALENDAR_LEGAL_END), re.S
)
CALENDAR_FAQ_RE = re.compile(r'<h2 id="faq[^"]*"', re.I)


def inject_calendar_legal_section(src, rel):
    """Kalendarz brań podaje terminy i wymiary — musi wskazać akt, z którego je bierze.

    Bez tego czytelnik dostaje twardą liczbę („wymiar 45 cm", „ochronny do 31 maja")
    bez możliwości sprawdzenia jej u źródła, a atlas tej samej ryby taki link ma.
    """
    src = calendar_legal_re.sub("", src)
    prefix = "poradniki/kalendarz-bran-"
    if not rel.startswith(prefix) or not rel.endswith(".html"):
        return src
    slug = rel[len(prefix):-len(".html")]
    record = FISH_BIOLOGICAL_REGISTRY.get(slug)
    if not record or slug not in FISH_LEGAL_SUMMARIES:
        return src
    match = CALENDAR_FAQ_RE.search(src)
    if not match:
        return src
    block = (
        CALENDAR_LEGAL_BEGIN
        + build_fish_legal_section(slug, record["group"])
        + CALENDAR_LEGAL_END
    )
    return src[:match.start()] + block + src[match.start():]

# Porównania obejmują wyłącznie cechy diagnostyczne opisane w FishBase.
# Nie zastępują oznaczenia przez ichtiologa ani oględzin całego okazu.
FISH_IDENTIFICATION_COMPARISONS = (
    {
        "pages": ("ploc", "wzdrega"),
        "names": ("Płoć", "Wzdręga"),
        "taxa": ("Rutilus rutilus", "Scardinius erythrophthalmus"),
        "rows": (
            ("Pysk", "Końcowy.", "Skierowany bardziej ku górze; dolna szczęka wysunięta."),
            ("Płetwy", "Pomarańczowo-czerwone.", "Czerwone, szczególnie płetwy brzuszne."),
        ),
        "caveat": "Barwa jest zmienna; bez widocznego pyska i płetw zwykłe zdjęcie może nie wystarczyć.",
    },
    {
        "pages": ("leszcz",),
        "names": ("Leszcz", "Krąp"),
        "taxa": ("Abramis brama", "Blicca bjoerkna"),
        "rows": (
            ("Sylwetka i płetwa odbytowa", "Ciało wyższe i silniej spłaszczone; płetwa odbytowa dłuższa.", "Ciało mniej wysokie; płetwa odbytowa krótsza."),
            ("Pysk", "Dolny, wysuwany rurkowato.", "Dolny, ale niewysuwany rurkowato."),
        ),
        "caveat": "Proporcje zależą od rozmiaru i ujęcia; pewne oznaczenie może wymagać policzenia promieni i łusek.",
    },
    {
        "pages": ("klen", "jaz"),
        "names": ("Kleń", "Jaź"),
        "taxa": ("Squalius cephalus", "Leuciscus idus"),
        "rows": (
            ("Łuski", "Ciemny pigment na wolnych krawędziach łusek często tworzy siateczkę.", "Brak regularnej czarnej siateczki na łuskach boków."),
            ("Głowa", "Masywniejsza, z wyraźnym podbródkiem.", "Bez tak wyraźnego podbródka."),
        ),
        "caveat": "Barwa i proporcje nakładają się; pojedyncze zdjęcie często nie daje pewnego oznaczenia.",
    },
    {
        "pages": ("brzana", "swinka"),
        "names": ("Brzana", "Świnka"),
        "taxa": ("Barbus barbus", "Chondrostoma nasus"),
        "rows": (
            ("Okolica pyska", "Dwie pary wąsików i gruba dolna warga z poduszeczką.", "Bez wąsików; dolna warga tworzy twardą, rogową krawędź."),
            ("Płetwy", "Barwa nie jest cechą rozstrzygającą.", "Płetwy piersiowe, brzuszne, odbytowa i ogonowa mogą być czerwone."),
        ),
        "caveat": "Wąsiki są mocniejszą cechą niż kolor, który zależy od środowiska i kondycji ryby.",
    },
    {
        "pages": ("sieja", "sielawa"),
        "names": ("Sieja", "Sielawa"),
        "taxa": ("Coregonus maraena", "Coregonus albula"),
        "rows": (
            ("Rozmiar według FishBase", "Maksymalna opublikowana długość: 130 cm.", "Maksymalna opublikowana długość: 48 cm; długość typowa: 20 cm."),
            ("Tryb życia i pokarm", "Bytuje m.in. w głębokich jeziorach; zjada bezkręgowce denne i małe ryby.", "Tworzy pelagiczne ławice w głębszych jeziorach; zjada planktonowe skorupiaki."),
        ),
        "caveat": "Rozmiar i środowisko nie wystarczają do oznaczenia; siejowate tworzą zmienne populacje i mogą się krzyżować.",
    },
    {
        "pages": ("troc-losos",),
        "names": ("Troć", "Łosoś"),
        "taxa": ("Salmo trutta", "Salmo salar"),
        "rows": (
            ("Plamy i pysk", "Plamy występują także poniżej linii bocznej; pysk zwykle sięga za oko.", "Zwykle mniej plam poniżej linii bocznej; pysk krótszy."),
            ("Płetwa tłuszczowa", "Krawędź bywa czerwonawa.", "Krawędź szara lub przezroczysta."),
        ),
        "caveat": "Cechy zmieniają się z wiekiem i fazą morską; fotografia bez skali i cech głowy nie daje pewności.",
    },
)

ROOT = os.path.dirname(os.path.abspath(__file__))
BEGIN = "  <!-- seo:meta begin (auto) -->"
END = "  <!-- seo:meta end (auto) -->"

INLINE_DIAGRAMS = {
    "spinning": ("Schemat prowadzenia przynęty spinningowej", ("spinning", "wobler", "guma", "przyneta")),
    "splawik": ("Schemat zestawu spławikowego", ("splawik", "splawikow")),
    "feeder": ("Schemat zestawu feederowego", ("feeder", "koszyczek", "method feeder")),
    "karpiowy": ("Schemat zestawu karpiowego", ("karpiow", "wlos", "kulka")),
    "warstwy-wody": ("Schemat warstw wody", ("glebokosc", "ton wody", "warstwy wody")),
    "stanowisko": ("Schemat organizacji stanowiska wędkarskiego", ("stanowisko", "brzeg", "miejsce lowienia")),
    "catch-release": ("Schemat spokojnego wypuszczania ryby", ("catch and release", "wypuszcz", "odczep")),
    "pakowanie": ("Schemat chłodnego pakowania ryby", ("chlodz", "transport ryby", "pakowanie ryby")),
    "wezel": ("Schemat wiązania węzła wędkarskiego", ("wezel", "wiazanie", "zylka")),
    "budowa-ryby": ("Podstawowe elementy budowy ryby", ("budowa ryby", "pletwa", "linia boczna")),
    "pomiar-ryby": ("Schemat prawidłowego pomiaru ryby", ("pomiar", "wymiar ochronny", "centymetr", "rekord", "dlugosc")),
    "przygotowanie-ryby": ("Schemat stanowiska przygotowania ryby", ("kuchnia", "filet", "deska", "przygotowanie ryby")),
    "echosonda": ("Schemat działania echosondy", ("echosonda", "sonar", "przetwornik")),
    "lodz": ("Schemat organizacji łowienia z łodzi", ("lodz", "lodka", "wioslo")),
    "sezon": ("Schemat czterech pór roku", ("sezon", "wiosna", "jesien", "zima")),
    "dobor-sprzetu": ("Schemat doboru podstawowego sprzętu", ("sprzet", "wedzisko", "kolowrotek", "dobor", "dobrac", "przynet")),
    "e-zezwolenie": ("Schemat obsługi e-zezwolenia", ("e zezwolenie", "zezwolenie online", "cyfryzac", "baza danych")),
    "monitoring-wody": ("Schemat monitoringu jakości wody", ("monitoring", "sniecie", "zanieczyszc", "probka wody", "glon")),
}

# Ilustracja śródtekstowa musi wyjaśniać konkretny fragment konkretnej strony.
# Brak wpisu oznacza świadomą decyzję „bez ilustracji” — nigdy losowy zamiennik
# z działu. Frazy kotwiczą obraz przy właściwym akapicie, a nie w równym odstępie.
INLINE_PAGE_VISUALS = {
    "techniki/spinning.html": (
        ("/assets/img/tematy/schemat-spinning.svg", ("techniki prowadzenia przynet", "zasada metody")),
        ("/assets/img/ryby/szczupak-wobler.jpg", ("czytanie wody", "gdzie stoi drapieznik")),
        ("/assets/img/ryby/szczupak-streamer.jpg", ("gatunki — jak je łowic spinningiem", "szczupak")),
    ),
    "techniki/splawik.html": (
        ("/assets/img/tematy/schemat-splawik.svg", ("budowa zestawu splawikowego", "wywazenie zestawu")),
    ),
    "techniki/feeder-dla-poczatkujacych.html": (
        ("/assets/img/tematy/schemat-feeder.svg", ("montaz krok po kroku", "prosty uklad przelotowy")),
    ),
    "techniki/karpiowanie.html": (
        ("/assets/img/tematy/schemat-karpiowy.svg", ("hair rig", "zestawu wlosowego")),
        ("/assets/img/ryby/karp-jezioro.jpg", ("wybor miejsca",)),
    ),
    "poradniki/catch-and-release.html": (
        ("/assets/img/tematy/schemat-catch-release.svg", ("mokre rece i kontakt z ryba", "reanimacja ryby")),
    ),
    "poradniki/wezly-wedkarskie.html": (
        ("/assets/img/tematy/schemat-wezel.svg", ("clinch i clinch ulepszony", "przywiazywania haczyka")),
    ),
    "poradniki/echosondy.html": (
        ("/assets/img/tematy/schemat-echosonda.svg", ("zasada dzialania", "impuls, echo")),
    ),
    "pierwsze-kroki/jak-nabic-przynete-i-odhaczyc-rybe.html": (
        ("/assets/img/tematy/schemat-catch-release.svg", ("bezpieczne odhaczanie ryby", "odloz rybe")),
    ),
    "narzedzia/czy-moge-zabrac-rybe.html": (
        ("/assets/img/tematy/schemat-pomiar-ryby.svg", ("jak prawidlowo zmierzyc rybe", "lista kontrolna przed zabraniem")),
    ),
    "aktualnosci/zezwolenia-online-2026.html": (
        ("/assets/img/tematy/schemat-e-zezwolenie.svg", ("oficjalne systemy", "przed zaplata i przed wyjazdem")),
    ),
    "aktualnosci/zakaz-polowu-bobr-lipiec-2026.html": (
        ("/assets/img/tematy/schemat-monitoring-wody.svg", ("obserwacja i pobor prob", "monitoring 20 lipca")),
    ),
    "kuchnia/przygotowanie-ryby.html": (
        ("/assets/img/tematy/schemat-pakowanie.svg", ("transport: lod i torba termiczna", "przechowywanie i transport")),
    ),
    # Zdjęcia z połowów i własnego sprzętu zamiast grafik ilustracyjnych —
    # proweniencja każdego pliku siedzi w assets/img/*/_meta.json.
    "ryby/szczupak.html": (
        ("/assets/img/ryby/szczupak-guma.jpg", ("metody i przynety",)),
        ("/assets/img/ryby/szczupak-ponton.jpg", ("taktyka łowienia",)),
        ("/assets/img/ryby/szczupak-las.jpg", ("rekordy polski",)),
    ),
    "ryby/karp.html": (
        ("/assets/img/ryby/karp-lustrzen-jesien.jpg", ("zerowanie według por roku",)),
        ("/assets/img/ryby/karp-mata-podbierak.jpg", ("metody i przynety",)),
        ("/assets/img/ryby/karp-podbierak-miarka.jpg", ("wartosc kulinarna",)),
    ),
    "ryby/karas.html": (
        ("/assets/img/ryby/karas-kukurydza.jpg", ("metody i przynety",)),
        ("/assets/img/ryby/karas-duzy.jpg", ("wyglad i rozpoznawanie",)),
    ),
    "ryby/okon.html": (
        ("/assets/img/ryby/okon-trawa.jpg", ("przepisy krajowe", "wymiar")),
    ),
    "ryby/lin.html": (
        ("/assets/img/ryby/lin-dlon.jpg", ("wyglad i rozpoznawanie",)),
        ("/assets/img/ryby/liny-trzy.jpg", ("srodowisko i wystepowanie",)),
        ("/assets/img/ryby/lin-dzien.jpg", ("metody i przynety",)),
    ),
    "ryby/jesiotr.html": (
        ("/assets/img/ryby/jesiotr-brzeg.jpg", ("wyglad i rozpoznawanie",)),
    ),
    "techniki/podlodowe.html": (
        ("/assets/img/tematy/mormyszki-podlodowe.jpg", ("mormyszki",)),
    ),
    "techniki/feeder.html": (
        ("/assets/img/tematy/leszcze-podbierak.jpg", ("feeder na jeziorze", "punkt necenia")),
    ),
    "sprzet/przynety.html": (
        ("/assets/img/tematy/gumy-kopyta.jpg", ("rodzaje gum",)),
        ("/assets/img/tematy/guma-glowka-dlon.jpg", ("dobor ciezaru głowki",)),
        ("/assets/img/tematy/blystki-wahadlowe.jpg", ("obrotowki i wahadłowki",)),
    ),
    "pierwsze-kroki/sprzet/przynety.html": (
        ("/assets/img/tematy/pudelko-przynet.jpg", ("plan pierwszych zakupow", "przechowywanie")),
    ),
    "sprzet/jak-wybrac-kolowrotek.html": (
        ("/assets/img/tematy/kolowrotek-ninja.jpg", ("kontrola przed zakupem", "parametry")),
    ),
    "sprzet/plecionki-zylki.html": (
        ("/assets/img/tematy/wedka-plecionka.jpg", ("plecionka",)),
    ),
    "poradniki/zanety-domowe.html": (
        ("/assets/img/tematy/zaneta-kukurydza.jpg", ("ziarna", "kukurydza")),
    ),
    "pierwsze-kroki/lowiska/jeziora.html": (
        ("/assets/img/tematy/jezioro-swit.jpg", ("stanowisko, wiatr i brzeg", "stanowisko")),
    ),
    "poradniki/pogoda-a-brania.html": (
        ("/assets/img/tematy/jezioro-deszcz.jpg", ("fronty atmosferyczne", "zachmurzenie")),
    ),
    "poradniki/lowienie-zima.html": (
        ("/assets/img/tematy/rozlewisko-zima.jpg", ("gdzie szukac ryb zima", "zimowiska")),
    ),
    "poradniki/wedkarstwo-z-brzegu.html": (
        ("/assets/img/tematy/jezioro-poranek.jpg", ("wybierz legalne i bezpieczne stanowisko", "czytaj brzeg")),
    ),
    "poradniki/lowienie-nocne.html": (
        ("/assets/img/ryby/liny-noc.jpg", ("organizacja stanowiska nocnego", "sygnalizacja bran noca")),
    ),
    "poradniki/wedkarstwo-z-lodzi.html": (
        ("/assets/img/ryby/szczupak-ponton-lato.jpg", ("ponton wedkarski",)),
    ),
    "sprzet/kolowrotki.html": (
        ("/assets/img/tematy/kolowrotek-golden-rn2000-szpula.jpg", ("szpula i nawoj",)),
    ),
    "sprzet/wedki.html": (
        ("/assets/img/tematy/wedka-kolowrotek-abu-garcia.jpg", ("przelotki, uchwyt kołowrotka",)),
        ("/assets/img/tematy/wedka-spinningowa-abu-garcia.jpg", ("spinning",)),
    ),
    "sprzet/akcesoria.html": (
        ("/assets/img/tematy/podbierak.jpg", ("podbierak i siatka",)),
    ),
}


def load_image_provenance():
    """Ładuje wyłącznie lokalne obrazy z manifestów ich źródła i licencji."""
    provenance = {}
    for directory in ("ryby", "aktualnosci", "tematy", "kuchnia", "humor"):
        manifest_path = Path(ROOT, "assets", "img", directory, "_meta.json")
        with manifest_path.open(encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
        for item in manifest.values():
            required = ("file", "artist", "license", "page")
            if not all(item.get(field) for field in required):
                raise ValueError(f"{manifest_path}: niepełna proweniencja obrazu")
            filename = item["file"]
            image_path = (
                "/" + filename.lstrip("/")
                if filename.startswith("assets/")
                else f"/assets/img/{directory}/{filename}"
            )
            provenance[image_path] = item
    for name, (alt, _terms) in INLINE_DIAGRAMS.items():
        image_path = f"/assets/img/tematy/schemat-{name}.svg"
        provenance.setdefault(image_path, {
            "file": image_path.lstrip("/"),
            "artist": SITE_NAME,
            "license": "Materiał własny",
            "page": BASE + image_path,
            "alt": alt,
            "kind": "schemat",
            "width": 1200,
            "height": 675,
        })
    return provenance


IMAGE_PROVENANCE = load_image_provenance()

# Kanoniczne adresy licencji dla nazw używanych w manifestach obrazów.
# Świadomie nie mapujemy „Materiału własnego" ani zgód indywidualnych —
# nie zadeklarujemy licencji, której nie potrafimy wskazać dokumentem.
LICENSE_URLS = {
    "CC0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "Public domain": "https://creativecommons.org/publicdomain/mark/1.0/",
    "CC BY 2.0": "https://creativecommons.org/licenses/by/2.0/",
    "CC BY 2.5": "https://creativecommons.org/licenses/by/2.5/",
    "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0/",
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-SA 2.0": "https://creativecommons.org/licenses/by-sa/2.0/",
    "CC BY-SA 2.5": "https://creativecommons.org/licenses/by-sa/2.5/",
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC BY-SA 3.0 de": "https://creativecommons.org/licenses/by-sa/3.0/de/",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
}


def image_license_fields(img_url):
    """Pola licencyjne ImageObject dla obrazu o znanej proweniencji.

    Google używa ich do oznaczenia licencji w Grafice. Zwraca pusty słownik,
    gdy obraz jest obcy (np. miniatura YouTube) albo gdy licencji nie da się
    wskazać adresem — lepiej nie deklarować nic niż zadeklarować nieprawdę.
    """
    if not img_url.startswith(BASE + "/"):
        return {}
    entry = IMAGE_PROVENANCE.get(img_url[len(BASE):])
    if not entry:
        return {}
    # Atrybucje prac pochodnych z Commons bywają wieloliniowe — w JSON-LD
    # muszą być jednym wierszem, inaczej wychodzi niepoprawny dokument.
    artist = " ".join(entry["artist"].split())
    attribution = {
        "creditText": artist,
        "creator": {"@type": "Person", "name": artist},
        "copyrightNotice": f'{artist} ({entry["license"]})',
    }
    license_url = LICENSE_URLS.get(entry["license"])
    if not license_url:
        # Materiał własny, grafika generowana i zgody indywidualne nie mają
        # adresu licencji, którym moglibyśmy się podeprzeć. Autorstwo znamy
        # jednak na pewno, więc podajemy samą atrybucję — wcześniej pomijaliśmy
        # ją razem z licencją i ImageObject wychodził bez żadnych danych.
        return attribution
    return {
        "license": license_url,
        "acquireLicensePage": entry["page"],
        **attribution,
    }


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

# --- Wspólna nawigacja: główne działy oraz stale widoczny pasek „Odkrywaj”. ---
# Każdy główny dział ma osobny link i pełne podmenu. Linki pomocnicze są
# widoczne w drugim rzędzie na desktopie i w osobnej grupie w menu mobilnym.
NAV_TOP = [
    ("Pierwsze kroki", "pierwsze-kroki/", "pierwsze-kroki"),
    ("Sprzęt", "sprzet/", "sprzet"),
    ("Techniki", "techniki/", "techniki"),
    ("Ryby", "ryby/", "ryby"),
    ("Łowiska", "lowiska/", "lowiska"),
    ("Poradniki", "poradniki/", "poradniki"),
]
# Limit pozycji w podmenu. Wcześniej menu powielało na każdej podstronie pełną
# listę działu (atlas ryb = 43 wpisy), przez co powtarzalna nawigacja ważyła
# więcej niż sama treść krótszych stron.
NAV_MAX_CHILDREN = 8

# Najważniejsze wejścia działu. Podmenu pokazuje tylko je — pełną listę stron
# udostępnia strona-indeks działu ("Zobacz cały dział"), do której prowadzi
# pierwsza pozycja każdego podmenu.
NAV_FEATURED = {
    "pierwsze-kroki": (
        "pierwsze-kroki/pierwszy-zestaw-wedkarski-budzet.html",
        "pierwsze-kroki/pozwolenia-karta-wedkarska.html",
        "pierwsze-kroki/jak-nabic-przynete-i-odhaczyc-rybe.html",
        "pierwsze-kroki/okresy-ochronne-wymiary.html",
        "pierwsze-kroki/twoj-pierwszy-wyjazd-na-ryby.html",
        "pierwsze-kroki/lowiska/jeziora.html",
        "pierwsze-kroki/lowiska/rzeki.html",
        "pierwsze-kroki/lowiska/stawy.html",
    ),
    "techniki": (
        "techniki/spinning.html", "techniki/feeder.html", "techniki/splawik.html",
        "techniki/karpiowanie.html", "techniki/muchowe.html", "techniki/podlodowe.html",
        "techniki/morskie.html", "techniki/feeder-dla-poczatkujacych.html",
    ),
    "ryby": (
        "ryby/szczupak.html", "ryby/sandacz.html", "ryby/okon.html", "ryby/karp.html",
        "ryby/leszcz.html", "ryby/ploc.html", "ryby/sum.html", "ryby/pstrag.html",
    ),
    "poradniki": (
        "poradniki/kalendarz-bran.html", "poradniki/pogoda-a-brania.html",
        "poradniki/wedkarstwo-z-brzegu.html", "poradniki/wedkarstwo-z-lodzi.html",
        "poradniki/wezly-wedkarskie.html", "poradniki/catch-and-release.html",
        "poradniki/lowienie-zima.html", "poradniki/lowienie-nocne.html",
    ),
    "lowiska": (
        "lowiska/mazowieckie.html", "lowiska/wielkopolskie.html", "lowiska/slaskie.html",
        "lowiska/malopolskie.html", "lowiska/pomorskie.html", "lowiska/lodzkie.html",
        "lowiska/dolnoslaskie.html", "lowiska/warminsko-mazurskie.html",
    ),
}
NAV_DISCOVER = [
    ("aktualnosci/", "Aktualności"),
    ("narzedzia/", "Narzędzia"),
    ("kuchnia/", "Kuchnia"),
    ("forum/", "Forum"),
    ("humor/", "Humor"),
    ("zakupy.html", "Zakupy"),
    ("zgodnie-z-zasadami.html", "Przepisy i dokumenty"),
]
nav_re = re.compile(r'(?:<a class="skip-link" href="#main-content">Przejdź do treści</a>)?<header class="site-header">.*?</header>', re.S)

# Linki formalne w stopce. Polityka prywatności i kontakt muszą być osiągalne
# z każdej strony — wymagają tego zarówno RODO, jak i zasady sieci reklamowych.
# Strony formalne nie są wpisami blogowymi — schema musi odpowiadać charakterowi
# treści, inaczej obiecuje artykuł tam, gdzie jest dokument albo dane kontaktowe.
FORMAL_PAGE_TYPES = {
    "polityka-prywatnosci.html": "WebPage",
    "kontakt.html": "ContactPage",
    "korekty.html": "WebPage",
}

FOOTER_LEGAL = [
    ("zgodnie-z-zasadami.html", "Przepisy i dokumenty"),
    ("polityka-prywatnosci.html", "Polityka prywatności"),
    ("kontakt.html", "Kontakt"),
    ("slownik.html", "Słownik"),
    ("korekty.html", "Rejestr korekt"),
    ("o-autorze.html", "O autorze"),
]
footer_legal_re = re.compile(r'<p class="footer-legal">.*?</p>', re.S)


def build_footer_legal(prefix):
    links = [
        f'<a href="{prefix}{href}">{html.escape(title)}</a>'
        for href, title in FOOTER_LEGAL
    ]
    links.append(
        '<a href="https://www.facebook.com/profile.php?id=61591546555168"'
        ' target="_blank" rel="noopener me">Facebook</a>'
    )
    return '<p class="footer-legal">' + " · ".join(links) + "</p>"

# Cache-busting lokalnych zasobów: wersja z hasha zawartości — po każdej zmianie
# link zmienia się, więc przeglądarki pobierają nowy plik (koniec ze starym cache).
def asset_content_hash(relative_path):
    try:
        with open(os.path.join(ROOT, relative_path), "rb") as asset:
            return hashlib.md5(asset.read()).hexdigest()[:8]
    except OSError:
        return "00000000"


CSS_VER = asset_content_hash("css/style.css")
JS_VER = asset_content_hash("js/main.js")


def versioned_asset_re(asset):
    return re.compile(
        rf'(?P<attribute>\b(?:href|src)=["\'])'
        rf'(?P<prefix>(?:(?:\./|\.\./)+|/)?)'
        rf'{re.escape(asset)}(?:[?#][^"\']*)?(?P<quote>["\'])',
        re.I,
    )


def normalize_versioned_asset(src, asset, version, pattern):
    return pattern.sub(
        lambda match: (
            f'{match.group("attribute")}{match.group("prefix")}{asset}'
            f'?v={version}{match.group("quote")}'
        ),
        src,
    )

def escape_metadata_attribute(value):
    """Koduje pełną, tekstową wartość meta dla bezpiecznego atrybutu HTML."""
    return html.escape(html.unescape(value), quote=True)



css_ver_re = versioned_asset_re("css/style.css")
js_ver_re = versioned_asset_re("js/main.js")
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


def nav_label(title):
    """Krótka etykieta do menu: bez nazwy serwisu i bez podtytułu po dwukropku."""
    label = re.sub(r"\s*\|\s*" + re.escape(SITE_NAME) + r"\s*$", "", title).strip()
    head = label.split(":", 1)[0].strip()
    return head if len(head) >= 4 else label


def _nav_children(section, prefix):
    available = {}
    for url, title in SECTION_PAGES.get(section, []):
        rel = url[len(BASE) + 1:] if url.startswith(BASE + "/") else url
        if rel and not rel.endswith("/"):  # pomiń stronę-indeks sekcji
            available[rel] = nav_label(title)
    featured = NAV_FEATURED.get(section, ())
    selected = [rel for rel in featured if rel in available]
    if len(selected) < NAV_MAX_CHILDREN:  # dział bez pełnej listy wyróżnionych
        selected.extend(rel for rel in available if rel not in selected)
    return [(prefix + rel, available[rel]) for rel in selected[:NAV_MAX_CHILDREN]]


def build_nav(prefix):
    items = []
    for label, href, section in NAV_TOP:
        kids = _nav_children(section, prefix)
        submenu_id = f"submenu-{section}"
        sub = "".join(
            f'<li><a href="{url}">{html.escape(title)}</a></li>'
            for url, title in kids
        )
        top_href = f"{prefix}{href}"
        control = (
            f'<a href="{top_href}">{html.escape(label)}</a>'
            f'<button class="submenu-toggle" type="button" aria-expanded="false" '
            f'aria-controls="{submenu_id}"><span class="sr-only">Rozwiń menu '
            f'{html.escape(label)}</span><span aria-hidden="true">▾</span></button>'
        )
        overview = (
            f'<li class="sub-overview"><a href="{top_href}">'
            f'Zobacz cały dział {html.escape(label)}</a></li>'
        )
        if len(kids) > 18:
            item_class = "has-sub nav-mega nav-mega-3"
        elif len(kids) > 10:
            item_class = "has-sub nav-mega nav-mega-2"
        else:
            item_class = "has-sub"
        items.append(
            f'<li class="{item_class}">{control}<ul id="{submenu_id}" class="sub">'
            f'{overview}{sub}</ul></li>'
        )
    discover_links = "".join(
        f'<li><a href="{prefix}{href}">{html.escape(title)}</a></li>'
        for href, title in NAV_DISCOVER
    )
    discover = (
        '<div class="nav-discover" aria-label="Odkrywaj">'
        '<span class="nav-discover-label">Odkrywaj</span>'
        f'<ul class="nav-discover-list">{discover_links}</ul></div>'
    )
    search_icon = (
        '<a class="nav-search" href="' + prefix + 'szukaj.html" aria-label="Szukaj">'
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<circle cx="11" cy="11" r="6.5"></circle>'
        '<path d="m16 16 4.5 4.5"></path></svg></a>'
    )
    return (
        '<a class="skip-link" href="#main-content">Przejdź do treści</a>'
        '<header class="site-header"><nav class="nav container" aria-label="Główna">'
        f'<a class="logo" href="{prefix}index.html"><span class="logo-mark">≈</span><span>FishPoint</span></a>'
        '<button class="nav-toggle" aria-expanded="false" aria-controls="nav-menu" '
        'aria-label="Otwórz menu">Menu</button>'
        f'<div id="nav-menu" class="nav-menu"><ul class="nav-sections">{"".join(items)}</ul>'
        f'{discover}</div>{search_icon}</nav></header>'
    )

title_re = re.compile(r"<title>(.*?)</title>", re.S)
desc_re = re.compile(r'<meta\s+name="description"\s+content="(.*?)"', re.S)
img_re = re.compile(r'<img[^>]+src="([^"]+)"', re.S)
block_re = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n", re.S)
tag_re = re.compile(r"<[^>]+>")
# Jedyna korekta metadanych utrzymuje pełne zdanie na wszystkich powierzchniach
# generowanych z opisu źródłowego; treść HTML pozostaje własnością redakcyjną.
METADATA_DESCRIPTION_SOURCES = {
    "kuchnia/smazony-okon-sandacz.html": (
        "Smażony okoń i sandacz krok po kroku: charakterystyka mięsa, przepis "
        "podstawowy ze składnikami i czasami smażenia oraz trzy warianty panierki."
    ),
}


# Trwałe metadane redakcyjne są źródłem dat publikacji i aktualizacji. Nie
# należą do bloku seo:auto, aby ponowne uruchomienie generatora ich nie usuwało.
CONTENT_META_RE = re.compile(
    r"<!--content-meta:\s*published=(\d{4}-\d{2}-\d{2});\s*modified=(\d{4}-\d{2}-\d{2})"
    r"(?:;\s*fp=([0-9a-f]{12}))?-->",
)
CONTENT_META_MARKER_RE = re.compile(r"<!--\s*content-meta:", re.I)

# Odcisk redakcyjnej treści strony. Wszystko, co generator sam wstrzykuje
# (bloki :auto, zarządzane metatagi, wersja arkusza), jest z niego wycięte —
# dzięki temu sama przebudowa nie podbija daty aktualizacji, a prawdziwa
# edycja tekstu tak.
AUTO_BLOCK_RE = re.compile(r"<!--([a-z-]+):auto-->.*?<!--/\1:auto-->", re.S)
# Blok metadanych w <head> używa innego formatu markera niż bloki w <body>.
SEO_BLOCK_RE = re.compile(
    r"<!--\s*seo:meta begin \(auto\)\s*-->.*?<!--\s*seo:meta end \(auto\)\s*-->", re.S)
CSS_VERSION_RE = re.compile(r"(\.css|\.js)\?v=[0-9a-f]+")


# Strony o stanie prawnym, których tytuł, opis i H1 niosą rok obowiązywania.
# Google Trends (sierpień 2026): samo „okresy ochronne" ma indeks 0, a całe
# „Zyskujące popularność" to warianty z rokiem — „okresy ochronne ryb 2024",
# „karta wędkarska 2026". Rok jest odświeżany przy każdej przebudowie, żeby
# strona nie zestarzała się w styczniu.
LEGAL_YEAR_PAGES = {
    "pierwsze-kroki/okresy-ochronne-wymiary.html",
    "narzedzia/okresy-ochronne.html",
    "pierwsze-kroki/pozwolenia-karta-wedkarska.html",
}
# Rok publikatora aktu (Dz.U. 2023 poz. 1373) nie jest rokiem obowiązywania.
LEGAL_CITATION_YEAR_RE = re.compile(r"(?:Dz\.\s?U\.|poz\.)\s*\d{4}")


def refresh_legal_year(src, path):
    """Podnosi rok w tytule, opisie i H1 stron o stanie prawnym."""
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    if rel not in LEGAL_YEAR_PAGES:
        return src
    year = str(datetime.date.today().year)

    def bump(match):
        text = match.group(0)
        # Rok publikatora maskujemy, żeby podmiana go nie dotknęła, i wracamy
        # z nim po odświeżeniu roku obowiązywania.
        shelf = []

        def stash(citation):
            shelf.append(citation.group(0))
            return f"\x00{len(shelf) - 1}\x00"

        text = LEGAL_CITATION_YEAR_RE.sub(stash, text)
        text = re.sub(r"\b20\d{2}\b", year, text)
        return re.sub(r"\x00(\d+)\x00", lambda m: shelf[int(m.group(1))], text)

    src = re.sub(r"<title>.*?</title>", bump, src, flags=re.S)
    src = re.sub(r'<meta\s+name="description"\s+content="[^"]*"', bump, src)
    src = re.sub(r"<h1\b[^>]*>.*?</h1>", bump, src, flags=re.S)
    return src


def editorial_fingerprint(src):
    """12 znaków sha256 z treści redakcyjnej, odporne na przebudowę.

    Poza odciskiem zostaje też wspólny chrome strony (nagłówek, menu, stopka).
    Przebudowa nawigacji dotyka wszystkich plików naraz, ale nie jest zmianą
    treści konkretnego artykułu i nie może podbijać jego daty aktualizacji.
    """
    body = src
    body = CONTENT_META_RE.sub("", body)
    body = AUTO_BLOCK_RE.sub("", body)
    body = SEO_BLOCK_RE.sub("", body)
    for tag in ("header", "nav", "footer"):
        body = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", body, flags=re.S | re.I)
    body = managed_meta_re.sub("", body)
    body = robots_meta_re.sub("", body)
    body = CSS_VERSION_RE.sub(r"\1", body)
    # optimize_images.py opakowuje obrazy w <picture> już po tym kroku.
    # Warianty AVIF/WebP są artefaktem budowania, nie zmianą redakcyjną.
    body = re.sub(r"</?picture\b[^>]*>", "", body)
    body = re.sub(r"<source\b[^>]*>", "", body)
    body = re.sub(r'\sdata-responsive-fallback="[^"]*"', "", body)
    body = re.sub(r'\s(?:srcset|sizes)="[^"]*"', "", body)
    body = re.sub(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>.*?</script>',
                  "", body, flags=re.S)
    body = re.sub(r'<link\b[^>]+rel=["\']canonical["\'][^>]*>', "", body)
    body = re.sub(r"<meta\b[^>]+name=[\"']description[\"'][^>]*>", "", body)
    body = re.sub(r"\s+", " ", body).strip()
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def write_content_meta(src, published, modified, fingerprint):
    """Podmienia komentarz content-meta na nowy, zachowując pozycję."""
    comment = (f"<!--content-meta: published={published}; "
               f"modified={modified}; fp={fingerprint}-->")
    new_src, count = CONTENT_META_RE.subn(comment, src, count=1)
    if count != 1:
        raise ValueError("nie udało się zapisać content-meta")
    return new_src


def content_change_date(path):
    """Data ostatniej realnej zmiany pliku: z gita, a dla niezacommitowanych
    zmian dzisiejsza. Nie używa mtime, bo przebudowa go nadpisuje."""
    rel = os.path.relpath(path, ROOT)
    if _git(["status", "--porcelain", "--", rel]):
        return datetime.date.today().isoformat()
    return _git(["log", "-1", "--format=%as", "--", rel]) or \
        datetime.date.today().isoformat()
robots_meta_re = re.compile(
    r'<meta\b(?=[^>]*\bname\s*=\s*["\']robots["\'])[^>]*>\s*', re.I)
managed_meta_re = re.compile(
    r'<meta\b(?=[^>]*(?:name|property)\s*=\s*["\']'
    r'(?:author|theme-color|twitter:[^"\']+|og:[^"\']+|article:[^"\']+)["\'])[^>]*>\s*',
    re.I,
)
youtube_nocookie_iframe_re = re.compile(
    r'''<iframe\b(?=[^>]*\bsrc\s*=\s*["']https?://(?:www\.)?youtube-nocookie\.com/embed/(?P<video_id>[A-Za-z0-9_-]{11})(?:\?[^"']*)?["'])(?=[^>]*\btitle\s*=\s*["'](?P<title>[^"']*)["'])[^>]*>\s*</iframe>''',
    re.I | re.S,
)

youtube_facade_re = re.compile(
    r'''(<button\b(?=[^>]*\bclass\s*=\s*["'][^"']*\byoutube-facade\b[^"']*["'])[^>]*>)(.*?)(</button>)''',
    re.I | re.S,
)


def ensure_youtube_facade_dimensions(src):
    """Nadaje stały rozmiar także fasadom utworzonym w poprzednich przebiegach."""
    def repl(match):
        def add_dimensions(image_match):
            attrs = re.sub(
                r'''\s+(?:width|height)\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)''',
                "",
                image_match.group(2),
                flags=re.I,
            )
            closing = " />" if image_match.group(3) == "/>" else ">"
            return f'{image_match.group(1)}{attrs.rstrip()} width="480" height="360"{closing}'

        content = re.sub(r"(<img\b)([^>]*?)(/?>)", add_dimensions, match.group(2), count=1, flags=re.I)
        return f"{match.group(1)}{content}{match.group(3)}"

    return youtube_facade_re.sub(repl, src)


article_image_re = re.compile(
    r'''<img\b(?=[^>]*\bclass\s*=\s*["'][^"']*\barticle-image\b[^"']*["'])(?=[^>]*\bsrc\s*=\s*["'](?P<src>[^"']+)["'])[^>]*>''',
    re.I | re.S,
)


def prioritize_local_lcp_image(src, page_dir):
    """Ustawia priorytet wyłącznie pierwszemu lokalnemu obrazowi artykułu."""
    for match in article_image_re.finditer(src):
        image_src = html.unescape(match.group("src"))
        if image_src.startswith(("http://", "https://", "//", "data:")):
            continue
        image_path = resolve_img(image_src, page_dir)
        if not os.path.isfile(os.path.join(ROOT, image_path.lstrip("/"))):
            continue
        tag = re.sub(
            r'''\s+(?:loading|fetchpriority)\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)''',
            "",
            match.group(0),
            flags=re.I,
        )
        tag = re.sub(r"\s*/?>\s*$", "", tag)
        tag = f'{tag} loading="eager" fetchpriority="high" />'
        return f"{src[:match.start()]}{tag}{src[match.end():]}", image_path
    return src, None


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
            f'alt="Miniatura filmu: {title_attr}" loading="lazy" decoding="async" width="480" height="360" />'
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
    published, modified, _fingerprint = matches[0]
    try:
        published_date = datetime.date.fromisoformat(published)
        modified_date = datetime.date.fromisoformat(modified)
    except ValueError as exc:
        raise ValueError(f"{path}: nieprawidłowa data content-meta") from exc
    if modified_date < published_date:
        raise ValueError(f"{path}: modified jest wcześniejsze niż published")
    return published, modified


def ensure_content_meta(src, path):
    """Utrzymuje trwałe daty redakcyjne strony.

    Data aktualizacji przestaje być zamrożona przy pierwszym wstrzyknięciu:
    przy każdej przebudowie porównujemy odcisk treści redakcyjnej z zapisanym
    i podbijamy `modified` wyłącznie wtedy, gdy tekst faktycznie się zmienił.
    Sama przebudowa (nowe bloki :auto, nowa wersja CSS) odcisku nie rusza.
    """
    if CONTENT_META_MARKER_RE.search(src):
        published, modified = parse_content_meta(src, path)
        stored = CONTENT_META_RE.search(src).group(3)
        current = editorial_fingerprint(src)
        if stored is None:
            # Migracja starej strony: zapisz odcisk, nie ruszając daty.
            src = write_content_meta(src, published, modified, current)
        elif stored != current:
            changed = content_change_date(path)
            modified = max(changed, published)
            src = write_content_meta(src, published, modified, current)
        return src, published, modified
    published, modified = git_dates(path)
    comment = (f"  <!--content-meta: published={published}; modified={modified}; "
               f"fp={editorial_fingerprint(src)}-->\n")
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


def collection_child_modified(section, root=ROOT):
    """Zwraca ostatnią realną zmianę bezpośredniej karty hubu."""
    dates = []
    for child in sorted((Path(root) / section).glob("*.html")):
        if child.name == "index.html":
            continue
        with open(child, encoding="utf-8") as f:
            _published, modified = parse_content_meta(f.read(), child)
        dates.append(modified)
    return max(dates, default=None)


# Idempotentny, widoczny ślad świeżości CollectionPage.
HUB_FRESHNESS_BEGIN, HUB_FRESHNESS_END = (
    "<!--hub-freshness:auto-->", "<!--/hub-freshness:auto-->"
)
hub_freshness_re = re.compile(
    re.escape(HUB_FRESHNESS_BEGIN) + r".*?" + re.escape(HUB_FRESHNESS_END), re.S
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
# Redakcyjne streszczenie strony: <!--tldr: własny tekst-->. Bez markera blok
# „W skrócie" nie powstaje — lepiej go nie mieć niż powielać opis meta.
EDITORIAL_TLDR_RE = re.compile(r"<!--\s*tldr:\s*(?!auto\b)(.+?)-->", re.S)


def editorial_tldr(src):
    match = EDITORIAL_TLDR_RE.search(src)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""
ARTICLE_VISUAL_BEGIN, ARTICLE_VISUAL_END = (
    "<!--article-visual:auto-->", "<!--/article-visual:auto-->"
)
article_visual_re = re.compile(
    re.escape(ARTICLE_VISUAL_BEGIN) + r".*?" + re.escape(ARTICLE_VISUAL_END), re.S
)
authored_article_figure_re = re.compile(
    r'<(?:figure|div)\b(?=[^>]*\bclass=["\'][^"\']*\barticle-figure\b)[^>]*>',
    re.I,
)
ARTICLE_CARD_OPEN_RE = re.compile(
    r'(<article\b(?=[^>]*\bclass=["\'][^"\']*\barticle-card\b)[^>]*>)',
    re.I,
)
ARTICLE_VISUAL_OPEN_RE = re.compile(
    r'(<article\b(?=[^>]*\bclass=["\'][^"\']*\barticle-card\b)[^>]*>|'
    r'<section\b(?=[^>]*\bclass=["\'][^"\']*\barticle-section\b)[^>]*>)',
    re.I,
)
INLINE_VISUAL_BEGIN, INLINE_VISUAL_END = (
    "<!--inline-visual:auto-->", "<!--/inline-visual:auto-->"
)
inline_visual_re = re.compile(
    re.escape(INLINE_VISUAL_BEGIN) + r".*?" + re.escape(INLINE_VISUAL_END), re.S
)


def strip_inline_visuals(src):
    """Usuwa wyłącznie w pełni generatorowe ilustracje śródtekstowe."""
    return inline_visual_re.sub("", src)
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

FIELD_NOTES_BEGIN, FIELD_NOTES_END = (
    "<!--field-notes:auto-->", "<!--/field-notes:auto-->"
)
field_notes_re = re.compile(
    re.escape(FIELD_NOTES_BEGIN)
    + r'<aside class="field-note field-note--(?:margin|sequence|record)">'
    + r'<span class="field-note-label" aria-hidden="true">.*?</span>'
    + r'(?P<content>.*?)</aside>'
    + re.escape(FIELD_NOTES_END),
    re.S,
)


def strip_field_notes(src):
    """Usuwa wyłącznie automatyczną ramę, pozostawiając źródłowy element."""
    return field_notes_re.sub(r"\g<content>", src)

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

FISH_BIOLOGY_BEGIN, FISH_BIOLOGY_END = (
    "<!--fish-biology:auto-->",
    "<!--/fish-biology:auto-->",
)
fish_biology_re = re.compile(
    re.escape(FISH_BIOLOGY_BEGIN) + r".*?" + re.escape(FISH_BIOLOGY_END),
    re.S,
)


def _biology_source_links(taxon, iucn_url=None):
    """Zwraca źródła taksonu i wyłącznie zweryfikowaną bezpośrednią kartę IUCN."""
    query = taxon.replace(" ", "%20")
    fishbase_slug = taxon.replace(" ", "_")
    sources = [
        (f"https://www.fishbase.se/summary/{fishbase_slug}.html", "FishBase"),
        (f"https://www.gbif.org/species/search?q={query}", "GBIF"),
    ]
    if iucn_url:
        sources.append((iucn_url, "IUCN Red List"))
    return tuple(sources)


def build_fish_biology_section(rel):
    """Buduje proweniencję biologiczną atlasu bez wniosków o połowie."""
    if not rel.startswith("ryby/"):
        return ""
    slug = os.path.splitext(os.path.basename(rel))[0]
    record = FISH_BIOLOGICAL_REGISTRY.get(slug)
    if not record:
        return ""
    taxa = record.get("taxa", (record["latin"],))
    configured_sources = record.get("biological_sources")
    if configured_sources:
        sources = " · ".join(
            f'<a href="{html.escape(url, quote=True)}" rel="noopener external" target="_blank">'
            f'{html.escape(label)}</a> — {html.escape(scope)}'
            for url, label, scope in configured_sources
        )
    else:
        sources = "".join(
            f'<a href="{html.escape(url, quote=True)}" rel="noopener external" target="_blank">'
            f'{html.escape(label)}: {html.escape(taxon)}</a>'
            for index, taxon in enumerate(taxa)
            for url, label in _biology_source_links(
                taxon, record.get("iucn_url") if index == 0 else None)
        )
    aliases = ", ".join(record["aliases"])
    if len(taxa) > 1:
        taxon_label = "Nazwy łacińskie"
        taxon_html = "; ".join(f"<i>{html.escape(taxon)}</i>" for taxon in taxa)
        alias_label = "Nazwy zwyczajowe / aliasy"
    else:
        taxon_label = "Nazwa łacińska"
        taxon_html = f"<i>{html.escape(taxa[0])}</i>"
        alias_label = "Alias"
    identification = next(
        (
            item
            for item in FISH_IDENTIFICATION_COMPARISONS
            if slug in item["pages"]
        ),
        None,
    )
    if identification:
        first_name, second_name = identification["names"]
        rows_html = "".join(
            "<tr>"
            f"<th scope=\"row\">{html.escape(feature)}</th>"
            f"<td>{html.escape(first)}</td>"
            f"<td>{html.escape(second)}</td>"
            "</tr>"
            for feature, first, second in identification["rows"]
        )
        comparison_sources = " · ".join(
            f'<a href="https://www.fishbase.se/summary/'
            f'{html.escape(taxon.replace(" ", "_"), quote=True)}.html" '
            f'rel="noopener external" target="_blank">'
            f'FishBase: <i>{html.escape(taxon)}</i></a>'
            for taxon in identification["taxa"]
        )
        comparison = (
            f'<h3>Jak odróżnić: {html.escape(first_name)} i '
            f'{html.escape(second_name)}</h3>'
            f'<div class="tool-table-wrap"><table class="tool-table">'
            f'<caption>Porównanie cech: {html.escape(first_name)} i {html.escape(second_name)}</caption>'
            f'<thead><tr><th scope="col">Cecha</th><th scope="col">{html.escape(first_name)}</th>'
            f'<th scope="col">{html.escape(second_name)}</th></tr></thead>'
            f'<tbody>{rows_html}</tbody></table></div>'
            f'<p><strong>Źródła cech:</strong> {comparison_sources}. '
            f'<strong>Dostęp:</strong> {BIOLOGICAL_SOURCE_DATE}.</p>'
            f'<p><strong>Granica oznaczenia:</strong> '
            f'{html.escape(identification["caveat"])} '
            f'Liczenie promieni lub łusek wymaga ostrego obrazu i praktyki; '
            f'cechy barwy i proporcji zależą od wieku, płci, populacji '
            f'i ubarwienia godowego.</p>'
        )
    else:
        compared_slug = record.get("compare")
        if compared_slug in FISH_BIOLOGICAL_REGISTRY and compared_slug in FISH_ENTITIES:
            compared = FISH_ENTITIES[compared_slug]["name"]
            comparison = (
                f'<h3>Porównanie taksonomiczne</h3><p>Porównaj z kartą '
                f'<a href="{compared_slug}.html">{html.escape(compared)}</a>. '
                f'Obie karty prowadzą do osobnych rekordów źródłowych; porównanie '
                f'nie jest kluczem oznaczania w terenie ani gwarancją wyniku połowu.</p>'
            )
        else:
            comparison = (
                '<h3>Porównanie taksonomiczne</h3><p>Brak wskazanej pary '
                'porównawczej: nie dodano podobnej ryby wyłącznie na podstawie nazwy.</p>'
            )
    caution = record.get("caution")
    caution_html = (
        f'<p><strong>Ograniczenie interpretacji:</strong> {html.escape(caution)}</p>'
        if caution else ""
    )
    legal_html = ""

    return (
        f'{FISH_BIOLOGY_BEGIN}<section class="source-box fish-biological-provenance" '
        f'aria-label="Pochodzenie danych biologicznych"><h2>Tożsamość biologiczna '
        f'i źródła</h2><p><strong>{taxon_label}:</strong> '
        f'{taxon_html}. <strong>Grupa atlasu:</strong> '
        f'{html.escape(record["group"])}. <strong>{alias_label}:</strong> '
        f'{html.escape(aliases)}.</p><p><strong>Źródła:</strong> {sources}. '
        f'<strong>Dostęp:</strong> {BIOLOGICAL_SOURCE_DATE}. '
        f'<strong>Zakres:</strong> {html.escape(BIOLOGICAL_SOURCE_SCOPE)}.</p>'
        f'{legal_html}{comparison}{caution_html}</section>{FISH_BIOLOGY_END}'
    )


def inject_fish_biology(src, rel):
    """Wstawia pojedynczy blok tylko do zarejestrowanej karty atlasu."""
    section = build_fish_biology_section(rel)
    if not section:
        return src
    return re.sub(r"(</article>)", section + r"\1", src, count=1)


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
    "pierwsze-kroki/jak-nabic-przynete-i-odhaczyc-rybe.html": {
        "answer": "Przygotuj narzędzia przed dotknięciem ryby, obchodź się z nią mokrymi dłońmi i odhaczaj bez szarpania. Gdy haczyk jest głęboko albo sytuacja wymaga siły, przerwij i wybierz rozwiązanie ograniczające uraz.",
        "table": ("Bezpieczna kolejność czynności", ("Krok", "Co zrobić", "Kiedy się zatrzymać"), (
            ("Przygotowanie", "Przed braniem miej pod ręką podbierak, miarkę i narzędzie do odhaczania.", "Nie improwizuj z rybą poza wodą."),
            ("Przynęta", "Załóż przynętę tak, aby grot haczyka pracował zgodnie z używanym zestawem.", "Gdy przynęta zasłania grot lub przeszkadza w zacięciu, popraw ją przed rzutem."),
            ("Odhaczanie", "Utrzymaj rybę spokojnie i wyjmij haczyk ruchem odwrotnym do jego wejścia.", "Nie wyrywaj głęboko osadzonego haczyka na siłę."),
        )),
        "mistakes": ("Rozpoczynanie odhaczania bez przygotowanego narzędzia.", "Dotykanie ryby suchymi dłońmi lub kładzenie jej na nieprzygotowanym podłożu.", "Szarpanie haczyka, gdy nie widać jego położenia."),
        "spot": ("Checklist przed odhaczeniem", ("Czy masz pod ręką narzędzie do odhaczania i miejsce, w którym ryba będzie bezpiecznie podparta?", "Czy potrafisz zobaczyć położenie haczyka bez rozwierania pyska na siłę?", "Czy możesz od razu zakończyć czynność i wypuścić rybę, gdy jest gotowa?")),
        "method": "Kolejność ogranicza pośpiech i manipulację rybą; nie zastępuje oceny gatunku, warunków ani zasad łowiska.",
        "source_prompt": "Przed wyjazdem sprawdź regulamin łowiska, zwłaszcza wymagania dotyczące haczyków, podbieraka i obchodzenia się z rybą.",
        "links": (("/pierwsze-kroki/okresy-ochronne-wymiary.html", "Ochrona ryb i limity"), ("/pierwsze-kroki/twoj-pierwszy-wyjazd-na-ryby.html", "Bezpieczny pierwszy wyjazd"), ("/sprzet/akcesoria.html", "Akcesoria do odhaczania")),
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
    "sprzet/pierwsza-wedka-spinningowa.html": {
        "answer": "Pierwszą wędkę spinningową dobieraj do wody, przynęt i sposobu łowienia, a następnie sprawdź, czy z kołowrotkiem oraz linką tworzy wygodny zestaw. Opis producenta porównuj z własnym zastosowaniem, nie z samą nazwą modelu.",
        "table": ("Wybór pierwszej wędki spinningowej", ("Pytanie", "Co sprawdzić", "Kolejny krok"), (
            ("Gdzie będziesz łowić?", "Dostęp do brzegu, przestrzeń do rzutu i rodzaj wody.", "Zawęź wybór do warunków, które masz najczęściej."),
            ("Jakich przynęt użyjesz?", "Zakres oznaczony na wędce oraz masę gotowego zestawu.", "Nie zakładaj, że jedno oznaczenie pasuje do każdej przynęty."),
            ("Czy zestaw jest wygodny?", "Uchwyt, wyważenie z kołowrotkiem i łatwość bezpiecznego transportu.", "Weź wędkę do ręki i oceń komplet przed zakupem."),
        )),
        "mistakes": ("Wybór wyłącznie po marce albo wyglądzie.", "Dobieranie wędki bez planu na używane przynęty i wodę.", "Kupowanie samego wędziska bez sprawdzenia zgodności z kołowrotkiem i linką."),
        "spot": ("Checklist przed zakupem", ("Czy wybrałeś miejsce i metodę, od których rzeczywiście zaczniesz?", "Czy porównałeś oznaczenia wędki z przynętami oraz gotowym zestawem?", "Czy sprawdziłeś wygodę chwytu i transportu?")),
        "method": "To filtr decyzji, nie test ani rekomendacja konkretnego modelu; ostateczny dobór zależy od warunków i sprzętu używanego razem z wędką.",
        "source_prompt": "Parametry oraz przeznaczenie porównaj z aktualną kartą producenta i sprawdź zasady połowu dla wybranej wody.",
        "links": (("/sprzet/kolowrotki.html", "Dobór kołowrotka"), ("/sprzet/plecionki-zylki.html", "Żyłka i plecionka"), ("/techniki/spinning.html", "Podstawy spinningu")),
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
    "techniki/feeder.html": (
        (
            "https://webep1.com/go/bbf47570c3",
            "Koszyki feederowe",
            "Porównaj koszyki do wody stojącej i rzeki, biorąc pod uwagę masę, dno oraz siłę nurtu.",
        ),
        (
            "https://webep1.com/go/fee88a95c3",
            "Zanęty",
            "Sprawdź zanęty, gliny i dodatki do przygotowania mieszanki feederowej.",
        ),
    ),
    "techniki/karpiowanie.html": (
        (
            "https://webep1.com/go/6608d83bc3",
            "Kulki i pellety",
            "Porównaj kulki proteinowe i pellety do nęcenia oraz prezentacji przynęty.",
        ),
    ),
    "techniki/spinning.html": (
        (
            "https://webep1.com/go/89081d9c3",
            "Wędki spinningowe",
            "Porównaj długość i ciężar wyrzutu wędki z przynętami oraz gatunkiem, który chcesz łowić.",
        ),
    ),
    "aktualnosci/zylka-czy-plecionka.html": (
        (
            "https://webep1.com/go/e7918164c3",
            "Żyłki, plecionki i fluorocarbon",
            "Porównaj rodzaje linek według metody, średnicy, rozciągliwości i warunków łowiska.",
        ),
    ),
    "aktualnosci/street-fishing-od-czego-zaczac.html": (
        (
            "https://webep1.com/go/92f2af80c3",
            "Plecaki wędkarskie",
            "Sprawdź plecaki ułatwiające mobilne łowienie i szybkie przemieszczanie się między miejscówkami.",
        ),
    ),
    "aktualnosci/jerki-na-szczupaka-poradnik.html": (
        (
            "https://webep1.com/go/89081d9c3",
            "Wędki spinningowe",
            "Porównaj mocniejsze wędki pod ciężar jerków i sposób prowadzenia przynęty.",
        ),
    ),
    "pierwsze-kroki/pierwszy-zestaw-wedkarski-budzet.html": (
        (
            "https://webep1.com/go/3b181da2c3",
            "Gotowy zestaw spinningowy",
            "Porównaj gotowe zestawy, jeśli chcesz zacząć bez dobierania każdego elementu osobno.",
        ),
    ),
    "aktualnosci/przyneta-na-spinning.html": (
        (
            "https://webep1.com/go/1a035dcfc3",
            "Przynęty sztuczne",
            "Porównaj typy przynęt dopiero po określeniu gatunku, łowiska i sposobu prowadzenia.",
        ),
        (
            "https://webep1.com/go/8877c7e5c3",
            "Woblery",
            "Sprawdź pracę i głębokość prowadzenia woblerów pod warunki opisane w poradniku.",
        ),
    ),
    "aktualnosci/mikroguma-dla-poczatkujacych.html": (
        (
            "https://webep1.com/go/885f8602c3",
            "Gumy i rippery",
            "Porównaj małe gumy według kształtu, rozmiaru i planowanego obciążenia.",
        ),
    ),
    "aktualnosci/okon-jesienia-mikroguma.html": (
        (
            "https://webep1.com/go/885f8602c3",
            "Gumy i rippery",
            "Dobierz rozmiar i kolor gumy do przejrzystości wody oraz aktywności okoni.",
        ),
    ),
    "aktualnosci/spinning-na-szczupaka-jesienia.html": (
        (
            "https://webep1.com/go/89081d9c3",
            "Wędki spinningowe",
            "Porównaj ciężar wyrzutu i moc wędki z masą jesiennych przynęt szczupakowych.",
        ),
        (
            "https://webep1.com/go/1a035dcfc3",
            "Przynęty sztuczne",
            "Sprawdź gumy, woblery i błystki po wybraniu głębokości oraz tempa prowadzenia.",
        ),
    ),
    "aktualnosci/na-co-bierze-karp-latem.html": (
        (
            "https://webep1.com/go/6608d83bc3",
            "Kulki i pellety",
            "Porównaj średnice i smaki kulek oraz pelletów do wybranego sposobu nęcenia.",
        ),
    ),
    "aktualnosci/karp-w-upaly-taktyka-na-lipiec.html": (
        (
            "https://webep1.com/go/6608d83bc3",
            "Kulki i pellety",
            "Dobierz ilość i rozmiar przynęty do temperatury, presji ryb i tempa żerowania.",
        ),
        (
            "https://webep1.com/go/b1df355ec3",
            "Wędki karpiowe",
            "Porównaj wędki dopiero po określeniu dystansu, masy zestawu i charakteru łowiska.",
        ),
    ),
    "aktualnosci/zawody-feederowe-poradnik.html": (
        (
            "https://webep1.com/go/b371c4e1c3",
            "Wędki feederowe",
            "Porównaj długość i ciężar wyrzutu pod dystans oraz regulamin zawodów.",
        ),
        (
            "https://webep1.com/go/c4f3584fc3",
            "Kołowrotki feederowe",
            "Dobierz pojemność szpuli i nawój do wędki oraz planowanej odległości łowienia.",
        ),
        (
            "https://webep1.com/go/bbf47570c3",
            "Koszyki feederowe",
            "Sprawdź koszyki po ustaleniu rodzaju dna, uciągu i dopuszczalnego zestawu.",
        ),
    ),
    "aktualnosci/relacja-nocna-zasiadka.html": (
        (
            "https://webep1.com/go/b1df355ec3",
            "Wędki karpiowe",
            "Porównaj parametry wędki z dystansem i masą zestawów opisanych w relacji.",
        ),
        (
            "https://webep1.com/go/6608d83bc3",
            "Kulki i pellety",
            "Sprawdź przynęty do punktowego, oszczędnego nęcenia na dłuższej zasiadce.",
        ),
    ),
    "sprzet/wedki.html": (
        (
            "https://webep1.com/go/89081d9c3",
            "Wędki spinningowe",
            "Porównaj długość, akcję i ciężar wyrzutu modeli spinningowych.",
        ),
        (
            "https://webep1.com/go/b371c4e1c3",
            "Wędki feederowe",
            "Sprawdź wędki feederowe według dystansu, koszyka i rodzaju łowiska.",
        ),
        (
            "https://webep1.com/go/b1df355ec3",
            "Wędki karpiowe",
            "Dobierz wędkę karpiową do dystansu, masy zestawu i techniki wywożenia.",
        ),
    ),
    "sprzet/kolowrotki.html": (
        (
            "https://webep1.com/go/f536215bc3",
            "Kołowrotki spinningowe",
            "Porównaj masę, przełożenie i hamulec do planowanego zestawu spinningowego.",
        ),
        (
            "https://webep1.com/go/c4f3584fc3",
            "Kołowrotki feederowe",
            "Sprawdź pojemność szpuli i nawój pod dystans łowienia feederem.",
        ),
        (
            "https://webep1.com/go/59f24cf1c3",
            "Kołowrotki karpiowe",
            "Dobierz kołowrotek karpiowy do dystansu, żyłki i masy całego zestawu.",
        ),
    ),
    "pierwsze-kroki/sprzet/wedki.html": (
        (
            "https://webep1.com/go/89081d9c3",
            "Wędki spinningowe",
            "Porównaj podstawowe parametry dopiero po wybraniu pierwszej metody łowienia.",
        ),
    ),
    "pierwsze-kroki/sprzet/kolowrotki.html": (
        (
            "https://webep1.com/go/f536215bc3",
            "Kołowrotki spinningowe",
            "Sprawdź modele pasujące wielkością i masą do pierwszej wędki spinningowej.",
        ),
    ),
    "pierwsze-kroki/sprzet/przynety.html": (
        (
            "https://webep1.com/go/1a035dcfc3",
            "Przynęty sztuczne",
            "Porównaj podstawowe rodzaje przynęt po wybraniu ryby i techniki łowienia.",
        ),
    ),
    "pierwsze-kroki/sprzet/akcesoria.html": (
        (
            "https://webep1.com/go/1bb1a3b3c3",
            "Akcesoria wędkarskie",
            "Uzupełnij pierwszy zestaw tylko o akcesoria potrzebne do wybranej metody.",
        ),
    ),
    "pierwsze-kroki/sprzet/zylki-plecionki.html": (
        (
            "https://webep1.com/go/e7918164c3",
            "Żyłki, plecionki i fluorocarbon",
            "Porównaj średnice i rodzaje linek po ustaleniu metody oraz wielkości ryb.",
        ),
    ),
    "zakupy.html": (
        (
            "https://webep1.com/go/3f03d6c5c3",
            "Gotowy zestaw feederowy",
            "Porównaj gotowe zestawy feederowe, gdy chcesz zacząć bez kompletowania każdego elementu osobno.",
        ),
        (
            "https://webep1.com/go/371f5146c3",
            "Gotowy zestaw method feeder",
            "Sprawdź gotowe zestawy method feeder do łowienia z koszykiem i zanętą.",
        ),
        (
            "https://webep1.com/go/3b181da2c3",
            "Gotowy zestaw spinningowy",
            "Zobacz gotowe zestawy spinningowe na pierwsze wyprawy za drapieżnikami.",
        ),
        (
            "https://webep1.com/go/59f24cf1c3",
            "Kołowrotki karpiowe",
            "Porównaj kołowrotki karpiowe dopasowane do cięższych zestawów i dużych dystansów.",
        ),
        (
            "https://webep1.com/go/b1df355ec3",
            "Wędki karpiowe",
            "Wybierz wędki karpiowe pod długość rzutu, ciężar zestawu i sposób łowienia.",
        ),
        (
            "https://webep1.com/go/6608d83bc3",
            "Kulki i pellety",
            "Sprawdź kulki proteinowe i pellety do budowania zanęty oraz przynęty.",
        ),
        (
            "https://webep1.com/go/663edc47c3",
            "Dodatki zanętowe i dipy",
            "Dobierz dodatki zanętowe i dipy do mieszanki, przynęty oraz warunków łowiska.",
        ),
        (
            "https://webep1.com/go/8877c7e5c3",
            "Woblery",
            "Porównaj woblery na drapieżniki według pracy, głębokości i sposobu prowadzenia.",
        ),
        (
            "https://webep1.com/go/d8ad8b8dc3",
            "Błystki",
            "Zobacz błystki do aktywnego szukania okoni, szczupaków i innych drapieżników.",
        ),
        (
            "https://webep1.com/go/c70fbfc0c3",
            "Twistery",
            "Wybierz twistery do jigowania i prowadzenia przy dnie.",
        ),
        (
            "https://webep1.com/go/74ac1044c3",
            "Jaskółki",
            "Sprawdź smukłe jaskółki do łowienia ostrożnych drapieżników.",
        ),
        (
            "https://webep1.com/go/4ea3bd70c3",
            "Żyłki",
            "Porównaj żyłki pod średnicę, rozciągliwość i planowaną metodę.",
        ),
        (
            "https://webep1.com/go/4d1297a8c3",
            "Fluorocarbon i mono",
            "Dobierz fluorocarbon lub przypon mono do przejrzystości wody i rodzaju zestawu.",
        ),
        (
            "https://webep1.com/go/405fc98ac3",
            "Haczyki, kotwiczki i główki jigowe",
            "Uzupełnij zestaw o haki, kotwiczki i główki jigowe do wybranej techniki.",
        ),
        (
            "https://webep1.com/go/d3253924c3",
            "Agrafki i krętliki",
            "Sprawdź agrafki, krętliki i kółka łącznikowe do szybkiej zmiany zestawu.",
        ),
        (
            "https://webep1.com/go/c8227fd2c3",
            "Podbieraki i osęki",
            "Wybierz podbierak lub osękę, które ułatwią bezpieczne podebranie ryby.",
        ),
        (
            "https://webep1.com/go/6ff7647bc3",
            "Wagi, miarki i chwytaki",
            "Zobacz narzędzia do ważenia, mierzenia i bezpiecznego przytrzymania ryby.",
        ),
        (
            "https://webep1.com/go/9ce264e7c3",
            "Pudełka i skrzynki",
            "Uporządkuj przynęty i drobne akcesoria w pudełkach oraz skrzynkach.",
        ),
        (
            "https://webep1.com/go/86ac9324c3",
            "Krzesełka i fotele wędkarskie",
            "Wybierz wygodne siedzisko na dłuższe zasiadki i wyprawy nad wodę.",
        ),
        (
            "https://webep1.com/go/fe23f399c3",
            "Torby wędkarskie",
            "Sprawdź torby do przenoszenia przynęt, akcesoriów i podstawowego wyposażenia.",
        ),
        (
            "https://webep1.com/go/92f2af80c3",
            "Plecaki wędkarskie",
            "Porównaj plecaki na mobilne wyprawy, gdy cały sprzęt musi być pod ręką.",
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
        eyebrow = "Sprzęt do poradnika"
        heading = "Porównaj pasujące kategorie sprzętu"
        intro = (
            "Poniższe kategorie odpowiadają sprzętowi omawianemu w tym poradniku. "
            "To linki afiliacyjne — FishPoint może otrzymać prowizję, "
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
    block_class = "info-block content-advantage"
    table_title, headers, rows = config["table"]
    table_class = "starter-kit" if "pierwszy-zestaw" in rel else "decision-table"
    table_html = (
        f'<section class="{table_class}" aria-label="{html.escape(table_title)}">'
        f'<h2>{html.escape(table_title)}</h2><table class="{table_class}">'
        f'<caption>{html.escape(table_title)}</caption><thead><tr>'
        + "".join(f'<th scope="col">{html.escape(cell)}</th>' for cell in headers)
        + "</tr></thead><tbody>"
        + "".join(
            '<tr><th scope="row">' + html.escape(row[0]) + "</th>"
            + "".join(f"<td>{html.escape(cell)}</td>" for cell in row[1:]) + "</tr>"
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
        f'{CONTENT_ADVANTAGE_BEGIN}<section class="{block_class}" '
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
    if rel == "pierwsze-kroki/index.html":
        return re.sub(r'(<section class="section\b[^>]*>)', block + r"\1", src, count=1)
    if FISHPOINT_METHOD_END in src:
        return src.replace(FISHPOINT_METHOD_END, FISHPOINT_METHOD_END + block, 1)
    if TLDR_END in src:
        return src.replace(TLDR_END, TLDR_END + block, 1)
    return ARTICLE_CARD_OPEN_RE.sub(r"\1" + block, src, count=1)

# Powiązania łączą hub sekcji z linkami modułów content-advantage oraz
# uzupełniającymi, redakcyjnie dobranymi linkami dla pogłębionych klastrów.
RELATED_LINKS = {
    "ryby/karp.html": (
        ("/techniki/karpiowanie.html", "Karpiowanie od podstaw"),
        ("/poradniki/kalendarz-bran-karp.html", "Kalendarz brań karpia"),
        ("/pierwsze-kroki/rodzaje-ryb/karp.html", "Karp dla początkujących"),
    ),
    "ryby/wzdrega.html": (
        ("/ryby/ploc.html", "Porównaj z płocią"),
    ),
    "ryby/jaz.html": (
        ("/ryby/klen.html", "Porównaj z kleniem"),
    ),
    "ryby/krap.html": (
        ("/ryby/leszcz.html", "Porównaj z leszczem"),
    ),
    "ryby/piskorz.html": (
        ("/ryby/koza.html", "Porównaj z kozą pospolitą"),
    ),
    "ryby/koza.html": (
        ("/ryby/piskorz.html", "Porównaj z piskorzem"),
    ),
    "ryby/brzana.html": (
        ("/ryby/swinka.html", "Porównaj ze świnką"),
    ),
    "ryby/swinka.html": (
        ("/ryby/brzana.html", "Porównaj z brzaną"),
    ),
    "ryby/sielawa.html": (
        ("/ryby/sieja.html", "Porównaj z sieją"),
    ),
    "ryby/sieja.html": (
        ("/ryby/sielawa.html", "Porównaj z sielawą"),
    ),
    "ryby/lipien.html": (
        ("/ryby/pstrag.html", "Porównaj z pstrągiem potokowym"),
    ),
    "ryby/amur.html": (
        ("/ryby/karp.html", "Porównaj z karpiem"),
    ),
    "ryby/klen.html": (
        ("/techniki/spinning.html", "Spinning na klenia"),
        ("/poradniki/kalendarz-bran-klen.html", "Kalendarz brań klenia"),
        ("/ryby/jaz.html", "Porównaj z jaziem"),
    ),
    "ryby/leszcz.html": (
        ("/techniki/feeder.html", "Feeder na leszcza"),
        ("/poradniki/kalendarz-bran-leszcz.html", "Kalendarz brań leszcza"),
        ("/ryby/krap.html", "Porównaj z krąpiem"),
    ),
    "ryby/lin.html": (
        ("/techniki/splawik.html", "Spławik na lina"),
        ("/poradniki/kalendarz-bran-lin.html", "Kalendarz brań lina"),
    ),
    "ryby/okon.html": (
        ("/techniki/spinning.html", "Spinning na okonia"),
        ("/poradniki/kalendarz-bran-okon.html", "Kalendarz brań okonia"),
    ),
    "ryby/ploc.html": (
        ("/techniki/splawik.html", "Spławik na płoć"),
        ("/poradniki/kalendarz-bran-ploc.html", "Kalendarz brań płoci"),
        ("/ryby/wzdrega.html", "Porównaj ze wzdręgą"),
    ),
    "ryby/pstrag.html": (
        ("/techniki/muchowe.html", "Wędkarstwo muchowe"),
        ("/poradniki/kalendarz-bran-pstrag.html", "Kalendarz brań pstrąga"),
        ("/ryby/lipien.html", "Porównaj z lipieniem"),
    ),
    "ryby/sandacz.html": (
        ("/techniki/spinning.html", "Spinning na sandacza"),
        ("/poradniki/kalendarz-bran-sandacz.html", "Kalendarz brań sandacza"),
    ),
    "ryby/sum.html": (
        ("/techniki/spinning.html", "Spinning na suma"),
        ("/poradniki/kalendarz-bran-sum.html", "Kalendarz brań suma"),
    ),
    "ryby/szczupak.html": (
        ("/techniki/spinning.html", "Spinning na szczupaka"),
        ("/poradniki/kalendarz-bran-szczupak.html", "Kalendarz brań szczupaka"),
    ),
    "techniki/feeder.html": (
        ("/techniki/feeder-dla-poczatkujacych.html", "Feeder dla początkujących"),
        ("/sprzet/wedki.html", "Jak dobrać wędkę"),
        ("/aktualnosci/zawody-feederowe-poradnik.html", "Przygotowanie do zawodów feederowych"),
    ),
    "techniki/spinning.html": (
        ("/aktualnosci/jaka-wedka-spinningowa-kupic.html", "Jak wybrać wędkę spinningową"),
        ("/sprzet/przynety.html", "Rodzaje przynęt"),
        ("/sprzet/plecionki-zylki.html", "Żyłka czy plecionka"),
    ),
    "techniki/karpiowanie.html": (
        ("/poradniki/kalendarz-bran-karp.html", "Kalendarz brań karpia"),
        ("/aktualnosci/na-co-bierze-karp-latem.html", "Przynęty na karpia latem"),
        ("/aktualnosci/karp-w-upaly-taktyka-na-lipiec.html", "Karp podczas upałów"),
    ),
    "sprzet/wedki.html": (
        ("/sprzet/jak-wybrac-kolowrotek.html", "Jak dobrać kołowrotek"),
        ("/pierwsze-kroki/pierwszy-zestaw-wedkarski-budzet.html", "Pierwszy zestaw wędkarski"),
        ("/narzedzia/dobor-sprzetu.html", "Dobór sprzętu"),
    ),
    "sprzet/kolowrotki.html": (
        ("/sprzet/jak-wybrac-kolowrotek.html", "Dobór kołowrotka krok po kroku"),
        ("/sprzet/plecionki-zylki.html", "Żyłki i plecionki"),
        ("/narzedzia/dobor-sprzetu.html", "Dobór sprzętu"),
    ),
    "sprzet/przynety.html": (
        ("/aktualnosci/przyneta-na-spinning.html", "Przynęta na spinning"),
        ("/aktualnosci/jak-dobrac-gume-na-drapieznika.html", "Jak dobrać gumę"),
        ("/aktualnosci/mikroguma-dla-poczatkujacych.html", "Mikroguma od podstaw"),
    ),
    "pierwsze-kroki/pierwszy-zestaw-wedkarski-budzet.html": (
        ("/pierwsze-kroki/sprzet/", "Elementy pierwszego zestawu"),
        ("/narzedzia/dobor-sprzetu.html", "Dobór sprzętu"),
        ("/sprzet/akcesoria.html", "Akcesoria wędkarskie"),
    ),
    "aktualnosci/wymiary-i-okresy-ochronne-2026.html": (
        ("/pierwsze-kroki/okresy-ochronne-wymiary.html", "Wymiary i okresy ochronne"),
        ("/narzedzia/okresy-ochronne.html", "Sprawdź okres ochronny"),
        ("/zgodnie-z-zasadami.html", "Przepisy i dokumenty"),
    ),
    "aktualnosci/gorne-wymiary-ochronne-2026.html": (
        ("/aktualnosci/wymiary-i-okresy-ochronne-2026.html", "Wymiary i okresy ochronne 2026"),
        ("/narzedzia/czy-moge-zabrac-rybe.html", "Czy mogę zabrać rybę"),
        ("/zgodnie-z-zasadami.html", "Przepisy i dokumenty"),
    ),
    "aktualnosci/zezwolenia-online-2026.html": (
        ("/pierwsze-kroki/pozwolenia-karta-wedkarska.html", "Pozwolenia i karta wędkarska"),
        ("/narzedzia/czy-moge-zabrac-rybe.html", "Czy mogę zabrać rybę"),
        ("/zgodnie-z-zasadami.html", "Przepisy i dokumenty"),
    ),
    "aktualnosci/wedkarstwo-morskie-dla-poczatkujacych.html": (
        ("/techniki/morskie.html", "Wędkarstwo morskie na Bałtyku"),
    ),
    "aktualnosci/rekord-okonia-2026.html": (
        ("/ryby/okon.html", "Atlas: okoń"),
        ("/poradniki/kalendarz-bran-okon.html", "Kalendarz brań okonia"),
        ("/techniki/spinning.html", "Spinning na okonia"),
    ),
    "aktualnosci/karp-w-upaly-taktyka-na-lipiec.html": (
        ("/ryby/karp.html", "Atlas: karp"),
        ("/poradniki/kalendarz-bran-karp.html", "Kalendarz brań karpia"),
        ("/techniki/karpiowanie.html", "Karpiowanie od podstaw"),
    ),
    "aktualnosci/spinning-na-szczupaka-jesienia.html": (
        ("/ryby/szczupak.html", "Atlas: szczupak"),
        ("/techniki/spinning.html", "Spinning od podstaw"),
        ("/aktualnosci/jaka-wedka-spinningowa-kupic.html", "Wybór wędki spinningowej"),
    ),
}
SECTION_PAGES = {}


FAQ_REPAIRS = {
    "aktualnosci/kalendarz-wedkarski-2026.html": (
        ("Czy kalendarz wędkarski gwarantuje brania?", "Nie. To plan przygotowania wyprawy; brania zależą od warunków, a legalność od przepisów i dokumentów konkretnej wody."),
        ("Czy w miesiącu poza ochroną wolno zabrać rybę?", "Nie automatycznie. Trzeba jeszcze sprawdzić wymiar, limit i lokalne warunki zezwolenia."),
        ("Gdzie sprawdzić ochronę odcinkową?", "W pełnym tekście § 7 rozporządzenia, a następnie w aktualnym zezwoleniu gospodarza."),
    ),
    "aktualnosci/zezwolenia-online-2026.html": (
        ("Czy potwierdzenie płatności jest zezwoleniem?", "Nie zawsze. Pobierz dokument wydany przez gospodarza i stosuj wskazany przez niego sposób okazania go przy kontroli."),
        ("Czy dziecko do 14 lat potrzebuje karty wędkarskiej?", "Nie, ale art. 7 ust. 3 wymaga połowu pod opieką pełnoletniej osoby posiadającej kartę wędkarską."),
        ("Czy e-zezwolenie PZW działa na każdej wodzie?", "Nie. Zawsze sprawdź właściwy okręg, wykaz wód i aktualne warunki konkretnego zezwolenia."),
    ),
    "aktualnosci/wymiary-i-okresy-ochronne-2026.html": (
        ("Co oznacza znak „—” przy okresie lub limicie?", "Oznacza brak wartości w danej rubryce tego zestawienia, nie automatyczną zgodę na połów lub zatrzymanie ryby."),
        ("Czy tabela obejmuje wyjątki odcinkowe?", "Tak, streszcza je, ale przy certcie, miętusie, pstrągu, łososiu i troci trzeba odczytać pełny § 6–7 aktu."),
        ("Czy lokalne zezwolenie może być ostrzejsze?", "Może ustanawiać warunki dostępu do konkretnej wody, np. limit lub górny wymiar; nie uchyla jednak przepisów krajowych."),
    ),
    "aktualnosci/kiedy-sezon-na-ryby-2026.html": (
        ("Czy po końcu okresu ochronnego sezon jest automatycznie otwarty?", "Nie. Należy sprawdzić § 7 ust. 2, odcinek wody, aktualne zezwolenie, regulamin i komunikaty gospodarza."),
        ("Dlaczego pstrąg ma dwie daty końca ochrony?", "§ 7 różnicuje wybrane odcinki Wisły, Sanu, Odry i Bystrzycy od pozostałych wód."),
        ("Czy kalendarz brań mówi, że połów jest legalny?", "Nie. Prognoza aktywności ryb nie zastępuje warunków prawnych i lokalnych dokumentów."),
    ),
    "aktualnosci/gorne-wymiary-ochronne-2026.html": (
        ("Czy istnieje jeden górny wymiar ochronny dla całego PZW?", "Nie. Górny wymiar wynika z dokumentu gospodarza konkretnej wody; nie wolno przenosić go między okręgami ani łowiskami."),
        ("Czy krajowy wymiar wystarcza, aby zatrzymać rybę?", "Nie. Trzeba spełnić równocześnie przepisy krajowe oraz aktualne warunki zezwolenia, regulaminu i komunikatów gospodarza."),
        ("Jak mierzyć rybę?", "Według § 6 ust. 2 rozporządzenia: od początku zamkniętego pyska do końca najdłuższego promienia płetwy ogonowej."),
    ),
}
FAQ_REPAIR_BEGIN = "<!--faq-repair:auto-->"
FAQ_REPAIR_END = "<!--/faq-repair:auto-->"
faq_repair_re = re.compile(
    re.escape(FAQ_REPAIR_BEGIN) + r".*?" + re.escape(FAQ_REPAIR_END), re.S
)


def visible_h1(src):
    """Zwraca jedyny, widoczny H1; jest kanoniczną nazwą dokumentu."""
    match = re.search(r"<h1\b[^>]*>(.*?)</h1>", src, re.S | re.I)
    return _clean(match.group(1)) if match else ""


def remove_legacy_jsonld(src, types):
    """Usuwa ręczne encje przejęte przez blok seo:auto, bez kasowania innych schema."""
    def replace(match):
        try:
            document = json.loads(match.group("json"))
        except json.JSONDecodeError:
            return match.group(0)
        if isinstance(document, dict) and document.get("@type") in types:
            return ""
        return match.group(0)

    return re.sub(
        r'<script\b[^>]*\btype=["\']application/ld\+json["\'][^>]*>\s*'
        r'(?P<json>.*?)\s*</script>\s*',
        replace,
        src,
        flags=re.S | re.I,
    )


def inject_visible_faq(src, rel):
    """Przywraca FAQ do HTML, zanim ta sama treść trafi do FAQPage."""
    src = faq_repair_re.sub("", src)
    pairs = FAQ_REPAIRS.get(rel)
    if not pairs or extract_faq(src):
        return src
    items = "".join(
        f'<section class="info-block"><h3>{html.escape(question)}</h3>'
        f'<p>{html.escape(answer)}</p></section>'
        for question, answer in pairs
    )
    block = (
        f'{FAQ_REPAIR_BEGIN}<h2 id="faq">FAQ — najczęstsze pytania</h2>'
        f'{items}{FAQ_REPAIR_END}'
    )
    article_start = re.search(r'<article class="article-card">', src)
    if not article_start:
        raise ValueError(f"{rel}: FAQ repair requires article-card")
    source_box = re.search(
        r'<(?:div|section)\b[^>]*\bclass=["\'][^"\']*\bsource-box\b[^"\']*["\'][^>]*>',
        src[article_start.end():],
        re.I,
    )
    if not source_box:
        raise ValueError(f"{rel}: FAQ repair requires a source-box")
    position = article_start.end() + source_box.start()
    return src[:position] + block + src[position:]


def llms_document_metadata(src, url, rel, published, modified, page_type):
    """Zwraca wyłącznie obserwowalną proweniencję pojedynczego dokumentu."""
    article = article_text(src)
    external = []
    for href, label in re.findall(r'<a\b[^>]*\bhref=["\'](https?://[^"\']+)["\'][^>]*>(.*?)</a>', src, re.S | re.I):
        source = (html.unescape(href), _clean(label))
        if source not in external:
            external.append(source)
    lines = [
        f"Canonical URL: {url}",
        f"Author: {AUTHOR_NAME}",
        f"Published: {published}",
        f"Modified: {modified}",
        f"Type: {page_type}",
        "Sources:",
    ]
    lines.extend(
        f"- [{label or href}]({href})" for href, label in external[:12]
    ) or lines.append("- No external source link is stated in the document.")
    if re.search(r"źródła?\s+i\s+(?:granice|weryfikacja)|granice informacji", article, re.I):
        lines.append("Evidence limitations: The document includes a visible sources-and-limitations note.")
    if re.search(r"\bkorekt", article, re.I):
        lines.append("Corrections: A correction policy or note is stated in the document.")
    if rel in AFFILIATE_LINKS:
        lines.append("Affiliation: The document contains an explicitly labelled affiliate section.")
    return lines


def short_title(title_txt):
    return title_txt.split(" — ")[0].split(" - ")[0]

def fish_about(fish):
    """Zwraca jedną encję Thing albo listę encji dla kart wielotaksonowych."""
    entities = [
        {"@type": "Thing", "name": fish["name"], "sameAs": fish["sameAs"]},
        *(
            {"@type": "Thing", "name": item["name"], "sameAs": item["sameAs"]}
            for item in fish.get("additional", ())
        ),
    ]
    return entities[0] if len(entities) == 1 else entities

def posting_about(rel, fish=None):
    """Łączy tylko jawnie zmapowane encje gatunku, metody i miejsca."""
    entities = []
    if fish:
        fish_entities = fish_about(fish)
        entities.extend(fish_entities if isinstance(fish_entities, list) else [fish_entities])
    method = METHOD_ENTITIES.get(rel)
    if method:
        entities.append({
            "@type": "DefinedTerm",
            "name": method,
            "url": BASE + "/" + rel,
            "inDefinedTermSet": BASE + "/techniki/",
        })
    entities.extend(PLACE_ENTITIES.get(rel, ()))
    if not entities:
        return None
    return entities[0] if len(entities) == 1 else entities


def article_text(src):
    """Czysty tekst semantycznej treści — do wordCount i llms-full.txt."""
    article = None if "data-water=" in src else re.search(
        r'<article class="article-card">(.*?)</article>', src, re.S
    )
    main = re.search(r"<main\b[^>]*>(.*?)</main>", src, re.S)
    match = article or main
    if not match:
        return ""
    chunk = match.group(1)
    chunk = re.sub(r"<script.*?</script>", " ", chunk, flags=re.S)
    chunk = re.sub(r"<style.*?</style>", " ", chunk, flags=re.S)
    chunk = toc_re.sub(" ", chunk)
    chunk = tldr_re.sub(" ", chunk)
    chunk = related_re.sub(" ", chunk)
    chunk = newsletter_re.sub(" ", chunk)
    chunk = giscus_re.sub(" ", chunk)
    chunk = affiliate_re.sub(" ", chunk)
    chunk = article_visual_re.sub(" ", chunk)
    chunk = inline_visual_re.sub(" ", chunk)
    return re.sub(r"\s+", " ", _clean(chunk)).strip()


RELATED_MAX = 4


def build_related(section, rel, url):
    """Hub sekcji oraz maksymalnie trzy strony-spokes.

    Pierwszeństwo mają wybory redakcyjne. Puste sloty domyka pierścień:
    strona linkuje do kolejnych stron tej samej sekcji, licząc cyklicznie od
    swojej pozycji. Dzięki temu każdy materiał ma link przychodzący, a ruch
    linkowy rozkłada się równo zamiast skupiać na kilku kartach.

    Zwraca (pozycje, nagłówek). Nagłówek mówi prawdę o zawartości: „Powiązane
    artykuły" tylko wtedy, gdy wszystkie spokes wskazano redakcyjnie.
    """
    related = [(BASE + f"/{section}/", f"Przegląd: {SECTIONS[section]}")]
    config = CONTENT_ADVANTAGES.get(rel, {})
    links = RELATED_LINKS.get(rel, ()) + config.get("links", ())
    for href, title in links:
        target = BASE + href
        if target != url and target not in {item[0] for item in related}:
            related.append((target, title))
        if len(related) == RELATED_MAX:
            return related, "Powiązane artykuły"

    siblings = SECTION_PAGES.get(section, ())
    position = next((i for i, item in enumerate(siblings) if item[0] == url), None)
    if position is None:
        heading = "Powiązane artykuły" if len(related) > 1 else f"Więcej w dziale: {SECTIONS[section]}"
        return related, heading

    seen = {item[0] for item in related}
    added = 0
    for offset in range(1, len(siblings)):
        target, title = siblings[(position + offset) % len(siblings)]
        if target in seen:
            continue
        related.append((target, title))
        seen.add(target)
        added += 1
        if len(related) == RELATED_MAX:
            break
    heading = f"Więcej w dziale: {SECTIONS[section]}" if added else "Powiązane artykuły"
    return related, heading


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
        u = absolute_url(img_path)
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

def absolute_url(value):
    """Normalizuje zewnętrzny URL albo publiczną ścieżkę do adresu absolutnego."""
    if value.startswith(("http://", "https://")):
        return value
    return BASE + (value if value.startswith("/") else "/" + value)


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


def jpeg_dimensions(image_path):
    """Odczytuje wymiary JPEG bez zależności zewnętrznej."""
    full_path = os.path.join(ROOT, image_path.lstrip("/"))
    try:
        with open(full_path, "rb") as image:
            if image.read(2) != b"\xff\xd8":
                return None
            while True:
                marker_start = image.read(1)
                while marker_start and marker_start != b"\xff":
                    marker_start = image.read(1)
                if not marker_start:
                    return None
                marker = image.read(1)
                while marker == b"\xff":
                    marker = image.read(1)
                if not marker or marker == b"\x00":
                    continue
                code = marker[0]
                if code in (0xD8, 0xD9) or 0xD0 <= code <= 0xD7:
                    continue
                length = image.read(2)
                if len(length) != 2:
                    return None
                payload_size = int.from_bytes(length, "big") - 2
                if payload_size < 5:
                    return None
                payload = image.read(payload_size)
                if len(payload) != payload_size:
                    return None
                if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                            0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    return (
                        int.from_bytes(payload[3:5], "big"),
                        int.from_bytes(payload[1:3], "big"),
                    )
    except OSError:
        return None
    return None


def select_article_visual(src, rel):
    """Zwraca manifestowy obraz dla nieilustrowanej karty albo None."""
    parts = rel.split("/")
    section = parts[0] if len(parts) > 1 else None
    if (section not in {"aktualnosci", "poradniki", "narzedzia", "techniki",
                        "sprzet", "pierwsze-kroki", "lowiska"}
            and rel not in TOOL_IMG
            or parts[-1] == "index.html"
            or not ARTICLE_VISUAL_OPEN_RE.search(src)
            or authored_article_figure_re.search(src)):
        return None
    image_path = TOOL_IMG.get(rel)
    og_marker = re.search(r"<!--\s*og-image:\s*([^\s>]+?)\s*-->", src)
    if not image_path and section == "aktualnosci" and og_marker:
        candidate = html.unescape(og_marker.group(1))
        if candidate.startswith("/"):
            image_path = candidate
    if not image_path:
        calendar = re.fullmatch(r"poradniki/kalendarz-bran-([a-z-]+)\.html", rel)
        if calendar:
            image_path = f"/assets/img/ryby/{calendar.group(1)}.jpg"
        else:
            image_path = TOOL_IMG.get(rel)
    provenance = IMAGE_PROVENANCE.get(image_path)
    dimensions = jpeg_dimensions(image_path) if provenance else None
    if not provenance or not dimensions:
        return None
    return image_path, provenance, dimensions


def inject_article_visual(src, rel, title_txt, modified):
    """Wstawia pojedynczy, podpisany obraz otwierający kartę artykułu."""
    src = article_visual_re.sub("", src)
    selected = select_article_visual(src, rel)
    if not selected:
        return src, None
    image_path, provenance, (width, height) = selected
    section = rel.split("/", 1)[0] if "/" in rel else None
    section_label = SECTIONS.get(section, SITE_NAME)
    read_minutes = max(1, math.ceil(len(article_text(src).split()) / 200))
    alt = provenance.get("alt") or f"Ilustracja do artykułu: {short_title(title_txt)}"
    credit = _credit_body(provenance)
    caption_note = (
        "Zdjęcie jest ilustracyjne i nie przedstawia konkretnego łowiska w tym regionie. "
        if section == "lowiska" else
        "Ilustracja. "
    )
    # Obraz wygenerowany nie jest zdjęciem — nazywanie go tak wprowadzałoby
    # czytelnika w błąd, zwłaszcza w materiale o konkretnym zdarzeniu.
    credit_label = (
        "Grafika" if "ygenerowano" in str(provenance.get("license", "")) else "Zdjęcie"
    )
    visual = (
        f'{ARTICLE_VISUAL_BEGIN}<figure class="article-lead-visual">'
        f'<div class="article-lead-frame"><img class="article-image" '
        f'src="{html.escape(image_path, quote=True)}" alt="{html.escape(alt, quote=True)}" '
        f'width="{width}" height="{height}" loading="eager" fetchpriority="high" '
        f'decoding="async" /><p class="article-lead-stamp"><span>{html.escape(section_label)}</span>'
        f'<span>{read_minutes} min czytania</span></p></div>'
        f'<figcaption class="article-lead-caption"><span>{caption_note}</span>'
        f'<span class="article-media-credit">{credit_label}: {credit}</span></figcaption>'
        f'<p class="article-signal-strip"><span>Dziennik wody</span>'
        f'<span>{html.escape(section_label)}</span><span><time datetime="{modified}">'
        f'{fmt_date_pl(modified)}</time></span></p></figure>{ARTICLE_VISUAL_END}'
    )
    return ARTICLE_VISUAL_OPEN_RE.sub(r"\1" + visual, src, count=1), image_path


class _ArticleDirectScanner(HTMLParser):
    """Zachowujący offsety skaner bez normalizowania HTML artykułu."""

    _VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"})

    def __init__(self, src):
        super().__init__(convert_charrefs=False)
        self.src = src
        self.line_offsets = [0]
        self.line_offsets.extend(
            offset + 1 for offset, char in enumerate(src) if char == "\n"
        )
        self.stack = []
        self.articles = []

    def _offset(self):
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    @staticmethod
    def _classes(attrs):
        return set((dict(attrs).get("class") or "").lower().split())

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        start = self._offset()
        parent = self.stack[-1] if self.stack else None
        parent_root = parent.get("root") if parent else None
        entry = {
            "tag": tag, "attrs": attrs, "start": start, "root": parent_root,
            "parent": parent, "children": [],
        }
        if tag == "article" and "article-card" in self._classes(attrs):
            entry["root"] = entry
            entry["depth"] = len(self.stack)
            self.articles.append(entry)
        elif parent_root and len(self.stack) == parent_root["depth"] + 1:
            entry["direct"] = True
            entry["order"] = len(parent_root["children"])
            parent_root["children"].append(entry)
        elif parent:
            parent["children"].append(entry)
        if tag not in self._VOID:
            self.stack.append(entry)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                end = self.src.find(">", self._offset()) + 1
                if end:
                    self.stack[index]["end"] = end
                del self.stack[index:]
                return
INLINE_BLOCKED_TOKENS = frozenset((
    "toc", "tldr", "faq", "source", "tool", "form", "table", "field-note",
    "related", "comments", "newsletter", "article-lead", "article-visual",
    "article-inline-visual", "content-advantage", "affiliate",
))


def inline_visual_count(words):
    """Kontrakt rytmu: zero do czterech ilustracji zależnie od długości tekstu."""
    if words < 450:
        return 0
    if words <= 850:
        return 1
    if words <= 1400:
        return 2
    if words <= 2200:
        return 3
    return 4


def _inline_plain(value):
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(char)
    )


def _inline_classes(item):
    return set((dict(item["attrs"]).get("class") or "").lower().split())


def _inline_blocked_item(item, src):
    classes = _inline_classes(item)
    fragment = src[item["start"]:item.get("end", item["start"])]
    return (
        item["tag"] in {"figure", "form", "table", "aside"}
        or bool(classes & INLINE_BLOCKED_TOKENS)
        or any(token in " ".join(classes) for token in INLINE_BLOCKED_TOKENS)
        or (item["tag"] == "section" and bool(re.search(r"<(?:figure|form|table)\b", fragment, re.I)))
    )


def _inline_in_blocked_ancestor(item, src):
    while item:
        if _inline_blocked_item(item, src):
            return True
        if item.get("root") is item:
            return False
        item = item.get("parent")
    return False

INLINE_BLOCKED_HEADING_RE = re.compile(
    r"<h[23]\b[^>]*>.*?(?:faq|źródł|zródl|source|narzędzi|narzedzi|"
    r"komentarz|powiązan).*?</h[23]>",
    re.I | re.S,
)


def _inline_blocked_heading_context(item, src):
    fragment = src[item["start"]:item.get("end", item["start"])]
    if INLINE_BLOCKED_HEADING_RE.search(fragment):
        return True
    parent = item.get("parent")
    if not parent:
        return False
    heading_tag = "h2" if parent.get("root") is parent else "h[23]"
    headings = list(re.finditer(
        rf"<{heading_tag}\b[^>]*>(.*?)</{heading_tag}>",
        src[parent["start"]:item["start"]], re.I | re.S,
    ))
    return bool(headings and INLINE_BLOCKED_HEADING_RE.search(headings[-1].group(0)))


def _inline_section(item):
    return item["tag"] == "section" and "article-section" in _inline_classes(item)


def _inline_candidate_items(article, src, auto_ranges):
    """Pełne, zbalansowane granice po akapicie albo sekcji; żadnych pół-tagów."""
    candidates = []

    def adjacent_safe(item):
        parent = item.get("parent")
        siblings = parent.get("children", ()) if parent else ()
        try:
            index = siblings.index(item)
        except ValueError:
            return False
        return not any(
            _inline_blocked_item(neighbor, src)
            for neighbor in siblings[max(0, index - 1):index] + siblings[index + 1:index + 2]
        )

    def visit(item):
        if ("end" not in item or _inline_in_blocked_ancestor(item, src)
                or _inline_blocked_heading_context(item, src)):
            return
        if any(item["start"] < end and start < item["end"] for start, end in auto_ranges):
            return
        parent = item.get("parent")
        parent_is_content = parent is article or (parent and _inline_section(parent))
        text = _field_note_text(src[item["start"]:item["end"]])
        if item["tag"] == "p" and parent_is_content and len(text) >= 140 and adjacent_safe(item):
            candidates.append({"start": item["end"], "item": item, "text": text})
        if (item.get("direct") and item["tag"] == "section"
                and len(text) >= 260 and adjacent_safe(item)):
            candidates.append({"start": item["end"], "item": item, "text": text})
        for child in item.get("children", ()):
            visit(child)

    for child in article["children"]:
        visit(child)
    return candidates


def _inline_dimensions(image_path, provenance):
    width, height = provenance.get("width"), provenance.get("height")
    if width and height:
        return int(width), int(height)
    return jpeg_dimensions(image_path)




def _inline_sources(rel, used_paths):
    """Zwraca wyłącznie ręcznie zatwierdzone media dla konkretnej strony."""
    sources = []
    for image_path, anchors in INLINE_PAGE_VISUALS.get(rel, ()):
        if image_path in used_paths or image_path not in IMAGE_PROVENANCE:
            continue
        provenance = IMAGE_PROVENANCE[image_path]
        dimensions = _inline_dimensions(image_path, provenance)
        if dimensions:
            sources.append((image_path, provenance, dimensions, anchors))
    return sources


def _inline_used_paths(src, page_dir):
    return {
        resolve_img(html.unescape(match.group(1)), page_dir)
        for match in img_re.finditer(src)
    }


def _inline_contextual_replacements(candidates, sources, wanted, article_start, src):
    """Łączy obraz tylko z akapitem, którego nagłówek lub tekst pasuje do kotwic."""
    if not candidates or not sources or not wanted:
        return []
    indexed = []
    for candidate in candidates:
        before = src[article_start:candidate["start"]]
        headings = list(re.finditer(r"<h[23]\b[^>]*>(.*?)</h[23]>", before, re.I | re.S))
        heading = _field_note_text(headings[-1].group(1)) if headings else ""
        context = _inline_plain(f"{heading} {candidate['text']}")
        progress = len(_field_note_text(before))
        indexed.append((progress, candidate, context))
    selected = []
    for source in sources:
        anchors = tuple(_inline_plain(anchor) for anchor in source[3])
        eligible = [
            (-sum(anchor in context for anchor in anchors), progress, candidate, source)
            for progress, candidate, context in indexed
            if any(anchor in context for anchor in anchors)
            and all(candidate is not chosen[2] for chosen in selected)
            and all(abs(progress - chosen[1]) >= 500 for chosen in selected)
        ]
        if eligible:
            selected.append(min(eligible, key=lambda item: (item[0], item[1])))
        if len(selected) >= wanted:
            break
    return [
        (candidate, source)
        for _negative_hits, _progress, candidate, source in sorted(
            selected, key=lambda item: item[1]
        )
    ]


# Zdjęcia własne i udostępnione przez czytelników nie mają zewnętrznego
# źródła — link „do licencji" prowadziłby wtedy z powrotem na tę samą stronę.
UNSOURCED_LICENSES = frozenset(("Materiał własny", "Publikacja za zgodą autora"))


def _credit_body(provenance):
    artist = html.escape(provenance["artist"])
    license_name = html.escape(provenance["license"])
    if provenance.get("license") in UNSOURCED_LICENSES:
        return f"{artist} ({license_name})"
    return (
        f'<a href="{html.escape(provenance["page"], quote=True)}" '
        f'rel="license external noopener">{artist} ({license_name})</a>'
    )


def _inline_credit(image_path, provenance):
    if provenance.get("kind") == "schemat":
        return "Schemat: FishPoint (materiał własny)"
    label = "Grafika" if "ygenerowano" in str(provenance.get("license", "")) else "Zdjęcie"
    return f"{label}: {_credit_body(provenance)}"


def _inline_markup(image_path, provenance, dimensions, title_txt, section, index):
    width, height = dimensions
    is_diagram = provenance.get("kind") == "schemat"
    alt = provenance.get("alt") or f"Ilustracja do artykułu: {short_title(title_txt)}"
    caption = provenance.get("caption", "").strip()
    if not caption:
        if is_diagram:
            name = Path(image_path).stem.removeprefix("schemat-")
            caption = INLINE_DIAGRAMS.get(name, ("Schemat pomocniczy do artykułu", ()))[0] + "."
        else:
            caption = f"Zdjęcie ilustracyjne: {alt.rstrip('.')}."
    if section == "lowiska" and not is_diagram:
        caption = (
            "Zdjęcie ilustracyjne; nie przedstawia konkretnego łowiska w tym regionie. "
            + alt.rstrip(".") + "."
        )
    side = "left" if index % 2 == 0 else "right"
    kind = "diagram" if is_diagram else "photo"
    return (
        f'{INLINE_VISUAL_BEGIN}<figure class="article-inline-visual article-inline-visual--{side} '
        f'article-inline-visual--{kind}"><div class="article-inline-frame">'
        f'<img class="article-inline-image" src="{html.escape(image_path, quote=True)}" '
        f'alt="{html.escape(alt, quote=True)}" width="{width}" height="{height}" '
        f'loading="lazy" decoding="async" /></div><figcaption class="article-inline-caption">'
        f'<span>{html.escape(caption)}</span><span class="article-inline-credit">{_inline_credit(image_path, provenance)}'
        f'</span></figcaption></figure>{INLINE_VISUAL_END}'
    )


def inject_inline_visuals(src, rel, title_txt, page_dir):
    """Odtwarza wyłącznie media przypisane do konkretnej strony i treści."""
    src = strip_inline_visuals(src)
    target = inline_visual_count(len(article_text(src).split()))
    if not target:
        return src
    scanner = _ArticleDirectScanner(src)
    scanner.feed(src)
    scanner.close()
    auto_ranges = _field_note_auto_ranges(src)
    article_candidates = []
    for article in scanner.articles:
        if "end" in article:
            article_candidates.append((
                article,
                _inline_candidate_items(article, src, auto_ranges),
            ))
    candidates = [item for _article, items in article_candidates for item in items]
    sources = _inline_sources(rel, _inline_used_paths(src, page_dir))
    chosen = min(target, len(candidates), len(sources))
    if not chosen:
        return src
    if len(article_candidates) == 1:
        article, items = article_candidates[0]
        replacements = _inline_contextual_replacements(
            items, sources, chosen, article["start"], src,
        )
    else:
        replacements = []
    if not replacements:
        return src
    section = rel.split("/", 1)[0] if "/" in rel else ""
    for index, (candidate, source) in reversed(list(enumerate(replacements))):
        image_path, provenance, dimensions, _anchors = source
        markup = _inline_markup(image_path, provenance, dimensions, title_txt, section, index)
        src = src[:candidate["start"]] + markup + src[candidate["start"]:]
    return src



def _field_note_text(fragment):
    """Tekst widoczny do kwalifikacji, nigdy do przepisywania."""
    return html.unescape(re.sub(r"<!--.*?-->|<[^>]+>", "", fragment, flags=re.S)).strip()


def _field_note_auto_ranges(src):
    return [
        match.span() for match in re.finditer(
            r"<!--([a-z0-9-]+):auto-->.*?<!--/\1:auto-->", src, re.I | re.S
        )
    ]


def _field_note_intersects(item, ranges):
    return any(item["start"] < end and start < item["end"] for start, end in ranges)


def _field_note_classes(item):
    return " ".join(dict(item["attrs"]).get("class", "").lower().split())


def _field_note_blocked(item):
    """Nie wchodź w sąsiedztwo modułów, mediów, narzędzi ani końcowych modułów."""
    classes = _field_note_classes(item)
    blocked_classes = (
        "tool", "source", "related", "faq", "content-advantage", "tldr", "toc",
        "newsletter", "comments", "article-lead", "article-visual", "video",
    )
    return item["tag"] in {"figure", "form", "table"} or any(
        token in classes for token in blocked_classes
    )


def _field_note_tail_heading(heading):
    return bool(re.search(r"\bfaq\b|\bźródł\w*|\bzrodl\w*", heading))


def _field_note_is_ordinary_paragraph(item, src, auto_ranges):
    if item["tag"] != "p" or _field_note_intersects(item, auto_ranges):
        return False
    classes = _field_note_classes(item)
    return not classes and bool(_field_note_text(src[item["start"]:item["end"]]))


def _field_note_safe_record(item, src, auto_ranges):
    if _field_note_intersects(item, auto_ranges):
        return None
    classes = _field_note_classes(item)
    raw = src[item["start"]:item["end"]].lower()
    if any(token in classes for token in ("tool", "content-advantage", "related", "faq")):
        return None
    if item["tag"] == "table":
        if re.search(r"<(?:form|input|select|textarea|button)\b", raw):
            return None
        return "Kontrola"
    if "source-list" in classes or "source-box" in classes:
        return "Źródła"
    return None


def _field_note_adjacent_safe(children, item):
    index = item["order"]
    neighbors = children[max(0, index - 1):index] + children[index + 1:index + 2]
    return not any(_field_note_blocked(neighbor) for neighbor in neighbors)


def _field_note_spaced(candidate, selected, paragraphs):
    """Dwa zwykłe akapity muszą pozostać między dwoma znakami rytmu."""
    for prior in selected:
        lo, hi = sorted((candidate["start"], prior["item"]["start"]))
        if sum(lo < paragraph["start"] < hi for paragraph in paragraphs) < 2:
            return False
    return True


def inject_field_notes(src, rel):
    """Wstawia maksymalnie dwa dyskretne znaczniki wyłącznie w karcie artykułu."""
    del rel  # Kontrakt jest czysto strukturalny, a nie oparty na slugach.
    src = strip_field_notes(src)
    scanner = _ArticleDirectScanner(src)
    scanner.feed(src)
    scanner.close()
    auto_ranges = _field_note_auto_ranges(src)
    replacements = []

    for article in scanner.articles:
        children = [item for item in article["children"] if "end" in item]
        if not children:
            continue
        headings = {}
        regions = []
        current = None
        for item in children:
            if item["tag"] == "h2":
                heading = _field_note_text(src[item["start"]:item["end"]]).lower()
                current = {"heading": heading, "paragraphs": []}
                regions.append(current)
                headings[item["order"]] = heading
            elif current and _field_note_is_ordinary_paragraph(item, src, auto_ranges):
                current["paragraphs"].append(item)

        ordinary = [
            item for item in children
            if _field_note_is_ordinary_paragraph(item, src, auto_ranges)
        ]
        selected = []

        def select(item, kind, label):
            if len(selected) >= 2 or not _field_note_adjacent_safe(children, item):
                return
            if not _field_note_spaced(item, selected, ordinary):
                return
            selected.append({"item": item, "kind": kind, "label": label})

        # Kolejność ma pierwszeństwo: istniejąca lista nie potrzebuje nowego tekstu.
        heading = ""
        for item in children:
            if item["tag"] == "h2":
                heading = headings.get(item["order"], "")
                continue
            if (
                item["tag"] in {"ol", "ul"}
                and not _field_note_tail_heading(heading)
                and not _field_note_intersects(item, auto_ranges)
                and (item["tag"] == "ol" or re.search(
                    r"\b(checklista|krok|instrukcja|przed wyjazdem|przed rzutem)\b",
                    heading,
                ))
            ):
                select(item, "sequence", "Kolejność" if item["tag"] == "ol" else "Kontrola")

        for region in regions:
            if _field_note_tail_heading(region["heading"]):
                continue
            paragraphs = region["paragraphs"]
            visible_lengths = [
                len(_field_note_text(src[item["start"]:item["end"]])) for item in paragraphs
            ]
            if len(paragraphs) < 3 or sum(visible_lengths) < 900:
                continue
            crossing = sum(visible_lengths) * .45
            total = 0
            for item, length in zip(paragraphs, visible_lengths):
                total += length
                if total >= crossing:
                    select(item, "margin", "Zapis terenowy")
                    break

        # Dowód źródłowy zostaje opcjonalnym drugim znakiem, nigdy modułem końcowym.
        heading = ""
        for item in children:
            if item["tag"] == "h2":
                heading = headings.get(item["order"], "")
                continue
            label = _field_note_safe_record(item, src, auto_ranges)
            if not label or _field_note_tail_heading(heading):
                continue
            select(item, "record", label)

        for choice in selected:
            item = choice["item"]
            original = src[item["start"]:item["end"]]
            replacements.append((
                item["start"], item["end"],
                f'{FIELD_NOTES_BEGIN}<aside class="field-note field-note--{choice["kind"]}">'
                f'<span class="field-note-label" aria-hidden="true">{choice["label"]}</span>'
                f'{original}</aside>{FIELD_NOTES_END}',
            ))

    for start, end, replacement in sorted(replacements, reverse=True):
        src = src[:start] + replacement + src[end:]
    return src


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
    src = refresh_legal_year(src, path)
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
    # Starsze wpisy zawierały ręczne kopie metadanych społecznościowych poza
    # blokiem seo:auto. Usuń je przed odtworzeniem jednego kanonicznego zestawu.
    src = managed_meta_re.sub("", src)
    # Wspólna nawigacja na każdej stronie — podmień istniejący nagłówek na
    # kanoniczny (z rozwijanymi działami). Prefiks ścieżek wg głębokości strony.
    depth = os.path.relpath(path, ROOT).replace(os.sep, "/").count("/")
    src = nav_re.sub(lambda m: build_nav("../" * depth), src, count=1)
    # Ten sam zestaw odnośników formalnych w stopce każdej strony.
    src = footer_legal_re.sub(
        lambda m: build_footer_legal("../" * depth), src, count=1)
    src = re.sub(r'<main(?![^>]*\bid=)([^>]*)>', r'<main id="main-content"\1>', src, count=1)
    src = canonicalize_internal_hrefs(src)
    src = normalize_versioned_asset(src, "css/style.css", CSS_VER, css_ver_re)
    src = normalize_versioned_asset(src, "js/main.js", JS_VER, js_ver_re)
    # usuń poprzednie wstrzyknięcia, by działać idempotentnie
    src = block_re.sub("", src)
    src = byline_re.sub("", src)
    src = toc_re.sub("", src)
    src = tldr_re.sub("", src)
    src = related_re.sub("", src)
    src = newsletter_re.sub("", src)
    src = giscus_re.sub("", src)
    src = fishpoint_method_re.sub("", src)
    src = fish_biology_re.sub("", src)
    src = content_advantage_re.sub("", src)
    src = affiliate_re.sub("", src)
    src = hub_freshness_re.sub("", src)
    src = article_visual_re.sub("", src)
    src = strip_inline_visuals(src)
    src = strip_field_notes(src)
    src = ensure_youtube_facade_dimensions(replace_youtube_nocookie_embeds(src))

    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    src = ensure_calendar_year(src, rel)

    tm = title_re.search(src)
    dm = desc_re.search(src)
    if not tm or not dm:
        return None
    src = remove_legacy_jsonld(src, {"BlogPosting"})
    if rel in FAQ_REPAIRS:
        src = remove_legacy_jsonld(src, {"FAQPage"})
    src = inject_visible_faq(src, rel)
    title_raw = tm.group(1).strip()
    desc_raw = METADATA_DESCRIPTION_SOURCES.get(rel, dm.group(1).strip())
    title_txt = html.unescape(title_raw)
    desc_txt = html.unescape(desc_raw)
    title_attr = escape_metadata_attribute(title_raw)
    desc_attr = escape_metadata_attribute(desc_raw)
    h1_txt = visible_h1(src) or short_title(title_txt)

    src = normalize_fish_legal_section(src, rel)
    src = inject_calendar_legal_section(src, rel)
    # Ujednolic sezonowa etykiete w hero: publikacja w lipcu nie udaje wrzesniowej daty.
    src = src.replace("wrzesień 2026", "sezon jesienny 2026")
    url = absolute_url(rel_url(path))


    parts = rel.split("/")
    section = parts[0] if len(parts) > 1 else None
    is_home = rel == "index.html"
    is_section_index = not is_home and rel.endswith("/index.html")
    collection_dir = os.path.dirname(rel)
    collection_modified = collection_child_modified(collection_dir) if is_section_index else None
    if collection_modified:
        freshness = (
            f'{HUB_FRESHNESS_BEGIN}<p class="article-meta hub-freshness">'
            f'<time datetime="{collection_modified}">Karty w dziale sprawdzone '
            f'{fmt_date_pl(collection_modified)}</time></p>{HUB_FRESHNESS_END}'
        )
        src = re.sub(r"(</h1>)", r"\1" + freshness, src, count=1)

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
        # „W skrócie" (TL;DR) — wyłącznie redakcyjny, z markera <!--tldr: ...-->.
        # Wcześniej blok powielał dosłownie meta description na 197 stronach, więc
        # nie streszczał niczego; powtarzalny wypełniacz zastąpił własny tekst.
        tldr_txt = editorial_tldr(src)
        if tldr_txt:
            tldr = (f'{TLDR_BEGIN}<aside class="tldr" aria-label="W skrócie">'
                    f'<p class="tldr-label">W skrócie</p><p>{html.escape(tldr_txt)}</p>'
                    f'</aside>{TLDR_END}')
            src = ARTICLE_CARD_OPEN_RE.sub(r"\1" + tldr, src, count=1)
        src = inject_fishpoint_method(src, rel)
        src = inject_fish_biology(src, rel)
        # Hub sekcji, powiązania redakcyjne, a na koniec pierścień sekcji.
        if section:
            rel_items, rel_heading = build_related(section, rel, url)
            if rel_items:
                links = "".join(
                    f'<a href="{u}">{html.escape(t)}</a>' for u, t in rel_items)
                label = html.escape(rel_heading)
                related = (f'{RELATED_BEGIN}<section class="related" aria-label="{label}">'
                           f'<h2>{label}</h2><div class="related-grid">{links}</div>'
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
    page_dir = os.path.dirname(path)
    src, visual_img_path = inject_article_visual(src, rel, title_txt, mtime)
    src = inject_inline_visuals(src, rel, title_txt, page_dir)
    src = inject_field_notes(src, rel)
    # Wstrzyknięty lead jest pierwszym lokalnym obrazem: jego dane obsługują
    # LCP, OpenGraph, schema.org oraz sitemapę obrazów.
    # LCP pozostaje przy leadzie; ilustracje śródtekstowe są zawsze lazy.
    src, lcp_img_path = prioritize_local_lcp_image(src, page_dir)
    im = img_re.search(src)
    img_path = resolve_img(im.group(1), page_dir) if im else DEFAULT_IMG
    if visual_img_path:
        img_path = visual_img_path
    elif rel in TOOL_IMG:
        img_path = TOOL_IMG[rel]
    else:
        m_og = re.search(r"<!--\s*og-image:\s*([^\s>]+?)\s*-->", src)
        if m_og:
            img_path = m_og.group(1)
    img_url = absolute_url(img_path)
    page_images = collect_images(src, page_dir)
    src = re.sub(r'<link\b(?=[^>]*\brel\s*=\s*["\']canonical["\'])[^>]*>\s*', "", src, flags=re.I)
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
        f'  <meta property="og:title" content="{title_attr}" />',
        f'  <meta property="og:description" content="{desc_attr}" />',
        f'  <meta property="og:url" content="{url}" />',
        f'  <meta property="og:image" content="{img_url}" />',
        '  <meta name="twitter:card" content="summary_large_image" />',
        f'  <meta name="twitter:title" content="{title_attr}" />',
        f'  <meta name="twitter:description" content="{desc_attr}" />',
        f'  <meta name="twitter:image" content="{img_url}" />',
    ]
    if og_type == "article":
        if lcp_img_path:
            head.append(f'  <link rel="preload" as="image" href="{lcp_img_path}" fetchpriority="high" />')
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
            "email": "maciejbaniewicz@gmail.com",
            # schema.org nie definiuje „author" dla Organization — rolę autora
            # niesie już „founder", a nadmiarowa właściwość wywala walidację.
            "founder": AUTHOR,
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
                "name": h1_txt,
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
                    "email": "maciejbaniewicz@gmail.com",
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
                **({"dateModified": collection_modified} if collection_modified else {}),
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
                    "name": h1_txt,
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
                        h1_txt, desc_txt, page_images, noindex, pubdate)
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
            }
            if first_alt:
                img_obj["caption"] = first_alt
            img_obj.update(image_license_fields(img_url))
            if fish:
                img_obj["about"] = fish_about(fish)
            posting = {
                "@context": "https://schema.org",
                "@type": FORMAL_PAGE_TYPES.get(rel, "BlogPosting"),
                "headline": h1_txt,
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
            kw = [h1_txt]
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
                        "name": h1_txt,
                        "description": desc_txt,
                        "inLanguage": "pl-PL",
                        "step": [
                            {"@type": "HowToStep", "position": i + 1, "text": s}
                            for i, s in enumerate(steps)
                        ],
                    }))
            # Encje emitujemy tylko z jawnych rejestrów: gatunek, metoda lub miejsce.
            about = posting_about(rel, fish)
            if about:
                posting["about"] = about
            head.append(jsonld(posting))

    head.append(END)
    block = "\n".join(head) + "\n"

    # wstaw przed </head>
    new_src = re.sub(r"\n?</head>", "\n" + block + "</head>", src, count=1)
    return (new_src, url, mtime, is_home or is_section_index,
            h1_txt, desc_txt, page_images, noindex, pubdate)



def run_inline_visual_fixtures():
    """Małe testy pamięciowe kontraktu śródtekstowych wizualizacji; bez builda."""
    thresholds = (
        (449, 0), (450, 1), (850, 1), (851, 2), (1400, 2),
        (1401, 3), (2200, 3), (2201, 4),
    )
    for words, expected in thresholds:
        if inline_visual_count(words) != expected:
            raise AssertionError(f"próg {words}: oczekiwano {expected}")

    def paragraph(words, topic="spinning feeder"):
        return "<p>" + " ".join([topic] * words) + ".</p>"

    unlisted = (
        '<article class="article-card">'
        + "".join(paragraph(70) for _ in range(7)) + "</article>"
    )
    if inject_inline_visuals(
        unlisted, "techniki/test.html", "Spinning i feeder", ROOT
    ) != unlisted:
        raise AssertionError("strona bez jawnego przypisania otrzymała losową ilustrację")

    regular = (
        '<article class="article-card"><figure class="article-lead-visual">'
        '<img src="/assets/img/ryby/szczupak.jpg" alt="lead" /></figure>'
        '<h2>Zasada metody</h2>'
        + "".join(paragraph(70) for _ in range(7)) + "</article>"
    )
    transformed = inject_inline_visuals(
        regular, "techniki/spinning.html", "Spinning", ROOT
    )
    generated = inline_visual_re.findall(transformed)
    if len(generated) != 1:
        raise AssertionError("jawnie przypisana strona nie otrzymała jednej ilustracji")
    if "/assets/img/tematy/schemat-spinning.svg" not in transformed:
        raise AssertionError("strona otrzymała ilustrację niezgodną z ręcznym przypisaniem")
    if '/assets/img/ryby/szczupak.jpg" alt="lead"' not in transformed:
        raise AssertionError("fixture utracił lead")
    if inject_inline_visuals(
        transformed, "techniki/spinning.html", "Spinning", ROOT
    ) != transformed:
        raise AssertionError("druga transformacja nie jest identyczna")
    if strip_inline_visuals(transformed) != regular:
        raise AssertionError("strip markerów nie odtwarza fixture")

    nested = (
        '<article class="article-card"><h2>Hair rig — istota zestawu włosowego</h2>'
        '<section class="article-section"><div>'
        + paragraph(260, "karp zestaw") + '</div></section>'
        '<section class="article-section"><div>'
        + paragraph(260, "karp zestaw") + "</div></section></article>"
    )
    nested_out = inject_inline_visuals(
        nested, "techniki/karpiowanie.html", "Zestaw karpiowy", ROOT
    )
    if not inline_visual_re.search(nested_out) or not re.search(
        r"</section><!--inline-visual:auto-->", nested_out
    ):
        raise AssertionError("nie obsłużono granicy zagnieżdżonej article-section")
    scanner = _ArticleDirectScanner(nested_out)
    scanner.feed(nested_out)
    scanner.close()
    if not scanner.articles or "end" not in scanner.articles[0]:
        raise AssertionError("wstawienie naruszyło zbalansowanie artykułu")
    print("Inline visual fixtures: ok")


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
        if "iucnredlist.org/search" in src:
            raise ValueError(f"{path}: odnośnik IUCN musi prowadzić bezpośrednio do /species/")
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
    import email.utils
    feed_root = ET.fromstring(contents["feed.xml"])
    feed_published = []
    for item in feed_root.findall("./channel/item"):
        link = item.findtext("link", "")
        pub_date = item.findtext("pubDate", "")
        rel = link.removeprefix(BASE).lstrip("/")
        if rel.endswith("/"):
            rel += "index.html"
        page_path = os.path.join(ROOT, rel)
        if not link.startswith(BASE + "/") or not os.path.isfile(page_path):
            raise ValueError(f"feed.xml: nieznany URL wpisu {link}")
        with open(page_path, encoding="utf-8") as f:
            published, _modified = parse_content_meta(f.read(), page_path)
        try:
            rss_date = email.utils.parsedate_to_datetime(pub_date).date().isoformat()
        except (TypeError, ValueError) as exc:
            raise ValueError(f"feed.xml: nieprawidłowy pubDate dla {link}") from exc
        if rss_date != published:
            raise ValueError(
                f"feed.xml: pubDate {rss_date} nie zgadza się z published "
                f"{published} dla {link}")
        feed_published.append(published)
    if feed_published != sorted(feed_published, reverse=True):
        raise ValueError("feed.xml: wpisy nie są posortowane od najnowszej publikacji")
    print(f"Walidacja artefaktów: ok ({len(html_paths)} stron)")




def llms_metadata_lines(canonical_url, newest_modified, scope):
    """Stałe metadane llms wyprowadzone wyłącznie z treści indeksowalnych."""
    return [
        f"> Język: pl-PL.",
        f"> Autor/redakcja: {AUTHOR_NAME}, redakcja {SITE_NAME}.",
        f"> Zakres: {scope}",
        f"> Najnowsza merytoryczna zmiana: {newest_modified}.",
        f"> Polityka źródeł i korekt: {BASE}/o-autorze.html.",
        f"> Kanoniczny URL: {canonical_url}.",
        "",
    ]


LATEST_NEWS_GRID_RE = re.compile(
    r'<div class="section-heading" id="najnowsze">.*?</div>\s*'
    r'<div class="blog-grid">(?P<cards>.*?)</div>',
    re.S,
)
HOME_NEWS_GRID_RE = re.compile(
    r'(?P<open><section id="aktualnosci"[^>]*>.*?<div class="blog-grid">)'
    r'(?P<cards>.*?)'
    r'(?P<close>\n\s*</div>\s*<p[^>]*><a class="btn btn-secondary" href="aktualnosci/">)',
    re.S,
)
BLOG_CARD_RE = re.compile(r'<article class="blog-card">.*?</article>', re.S)


def sync_home_news(limit=6):
    """Synchronizuje karty strony głównej z początkiem sekcji „Najnowsze”."""
    news_path = Path(ROOT) / "aktualnosci" / "index.html"
    home_path = Path(ROOT) / "index.html"
    news_src = news_path.read_text(encoding="utf-8")
    home_src = home_path.read_text(encoding="utf-8")

    latest_grid = LATEST_NEWS_GRID_RE.search(news_src)
    if not latest_grid:
        raise ValueError(f"{news_path}: brak sekcji najnowszych aktualności")
    cards = BLOG_CARD_RE.findall(latest_grid.group("cards"))[:limit]
    if len(cards) != limit:
        raise ValueError(f"{news_path}: oczekiwano co najmniej {limit} kart aktualności")

    home_cards = []
    for card in cards:
        card = card.replace("../assets/", "/assets/")
        card = re.sub(
            r'href="(?!https?://|/|#|aktualnosci/)([^"]+\.html(?:#[^"]*)?)"',
            r'href="aktualnosci/\1"',
            card,
        )
        home_cards.append("        " + card.strip().replace("\n", "\n        "))

    payload = (
        "\n        <!-- home-news:auto begin -->\n"
        + "\n".join(home_cards)
        + "\n        <!-- home-news:auto end -->"
    )
    updated, count = HOME_NEWS_GRID_RE.subn(
        lambda match: match.group("open") + payload + match.group("close"),
        home_src,
        count=1,
    )
    if count != 1:
        raise ValueError(f"{home_path}: brak siatki aktualności strony głównej")
    if updated != home_src:
        home_path.write_text(updated, encoding="utf-8")


def main():
    sync_home_news()
    pages = []
    for dirpath, _, files in os.walk(ROOT):
        if "/.git" in dirpath:
            continue
        for fn in files:
            if fn.endswith(".html") and fn != "404.html":
                pages.append(os.path.join(dirpath, fn))
    pages.sort()

    # Pre-pass: odśwież daty i odciski treści na dysku, zanim cokolwiek zacznie
    # z nich liczyć. Hub bierze swoją świeżość z max daty dzieci, więc gdyby
    # dziecko dostawało nową datę dopiero w swoim przebiegu, hub zbudowany
    # wcześniej zapisałby wartość nieaktualną i kontrakt świeżości by pękł.
    for p in pages:
        with open(p, encoding="utf-8") as f:
            before = f.read()
        after, _published, _modified = ensure_content_meta(
            refresh_legal_year(before, p), p)
        if after != before:
            with open(p, "w", encoding="utf-8") as f:
                f.write(after)

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
        s404 = re.sub(r'<main(?![^>]*\bid=)([^>]*)>', r'<main id="main-content"\1>', s404, count=1)
        s404 = canonicalize_internal_hrefs(s404)
        s404 = normalize_versioned_asset(s404, "css/style.css", CSS_VER, css_ver_re)
        s404 = normalize_versioned_asset(s404, "js/main.js", JS_VER, js_ver_re)
        with open(p404, "w", encoding="utf-8") as f:
            f.write(s404)

    urls = []
    changed = 0
    for p in pages:
        res = build(p)
        if not res:
            print("POMINIĘTO (brak title/desc):", p)
            continue
        new_src, url, mtime, is_index, title_txt, desc_txt, page_images, noindex, pubdate = res
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_src)
        if not noindex:
            section = rel_url(p).strip("/").split("/")[0] if rel_url(p) != "/" else ""
            urls.append((url, mtime, is_index, rel_url(p), title_txt, desc_txt, section, page_images, pubdate))
        changed += 1

    # sitemap.xml (z rozszerzeniem Image — indeksacja w Grafice Google)
    def xesc(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
          ' xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    total_imgs = 0
    for url, mtime, is_index, rp, _title, _desc, _sec, imgs, _pubdate in sorted(urls, key=lambda t: t[0]):
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
    newest_modified = max(mtime for _url, mtime, *_rest in urls)
    ll = [
        "# FishPoint",
        "",
        "> FishPoint to polski poradnik wędkarski: dobór sprzętu, atlas ryb "
        "słodkowodnych, techniki połowu, opisy łowisk, poradniki dla początkujących "
        "i przepisy kuchni rybnej.",
        "",
        *llms_metadata_lines(
            BASE + "/llms.txt", newest_modified,
            "Mapa wszystkich indeksowalnych stron FishPoint.",
        ),
    ]
    by_sec = {}
    home = None
    for url, mtime, is_index, rp, title, desc, sec, _imgs, _pubdate in sorted(urls):
        if rp == "/":
            home = (url, title, desc)
            continue
        # Strony w korzeniu nie mają działu — bez tego ich nazwa pliku trafiała
        # do llms.txt jako nagłówek sekcji („## Zgodnie-z-zasadami.html").
        key = sec if sec in SECTIONS else "informacje"
        by_sec.setdefault(key, []).append((url, title, desc, is_index))
    if home:
        ll.append(f"- [{home[1]}]({home[0]}): {home[2]}")
        ll.append("")
    for sec in sorted(by_sec):
        ll.append(f"## {SECTIONS.get(sec, 'Informacje o serwisie')}")
        ll.append("")
        for url, title, desc, is_index in by_sec[sec]:
            short = title.split(" — ")[0].split(" - ")[0]
            ll.append(f"- [{short}]({url}): {desc}")
        ll.append("")
    with open(os.path.join(ROOT, "llms.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(ll).rstrip() + "\n")

    # llms-full.txt — pełny zrzut każdej indeksowalnej strony bez progów długości.
    full = [
        "# FishPoint — pełna treść",
        "",
        "> Kompletny, tekstowy zrzut indeksowalnej treści serwisu FishPoint.",
        "",
        *llms_metadata_lines(
            BASE + "/llms-full.txt", newest_modified,
            "Pełny tekst wszystkich indeksowalnych stron FishPoint.",
        ),
    ]
    full_n = 0
    for url, modified, is_index, rp, title, _desc, sec, _imgs, published in sorted(urls):
        rel_path = rp.lstrip("/") or "index.html"
        if rel_path.endswith("/"):
            rel_path += "index.html"
        path = os.path.join(ROOT, rel_path)
        with open(path, encoding="utf-8") as f:
            src = f.read()
        page_type = (
            "WebSite" if rp == "/" else
            "CollectionPage" if is_index else
            "Recipe" if sec == "kuchnia" else
            "BlogPosting"
        )
        full.append(f"## {title}")
        full.extend(llms_document_metadata(
            src, url, rel_path, published, modified, page_type
        ))
        full.append("")
        full.append(article_text(src))
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
    blog.sort(key=lambda t: t[8], reverse=True)
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
        rss.append(f'    <lastBuildDate>{rfc822(max(u[1] for u in blog))}</lastBuildDate>')
    for url, _mtime, _is_index, _rp, title, desc, _sec, _imgs, pubdate in blog:
        rss += ['    <item>',
                f'      <title>{xesc(title)}</title>',
                f'      <link>{url}</link>',
                f'      <guid isPermaLink="true">{url}</guid>',
                f'      <pubDate>{rfc822(pubdate)}</pubDate>',
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
    elif sys.argv[1:] == ["--test-inline-visuals"]:
        run_inline_visual_fixtures()
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("użycie: seo_inject.py [--validate|--test-inline-visuals]")
