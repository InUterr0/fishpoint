#!/usr/bin/env python3
"""Generuje 12 stron „Jakie ryby można łowić w <miesiącu>”.

Listy gatunków powstają wyłącznie z rejestru prawnego seo_inject.py
(Dz.U. 2023 poz. 1373, § 6–8), więc strony nie wprowadzają żadnego nowego
twierdzenia prawnego. Miesiąc po miesiącu zmienia się skład list, a część
opisowa jest pisana ręcznie dla każdego miesiąca.

Uruchom przed seo_inject.py — generator tworzy źródło strony, a seo_inject
dokłada nawigację, metadane, TL;DR, spis treści i dane strukturalne.
"""
import html
import os
import re
import sys

import seo_inject

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "poradniki")

# Miesiące: numer, mianownik, miejscownik, slug URL (miejscownik bez znaków diakrytycznych).
MONTHS = [
    (1, "styczeń", "styczniu", "styczniu"),
    (2, "luty", "lutym", "lutym"),
    (3, "marzec", "marcu", "marcu"),
    (4, "kwiecień", "kwietniu", "kwietniu"),
    (5, "maj", "maju", "maju"),
    (6, "czerwiec", "czerwcu", "czerwcu"),
    (7, "lipiec", "lipcu", "lipcu"),
    (8, "sierpień", "sierpniu", "sierpniu"),
    (9, "wrzesień", "wrześniu", "wrzesniu"),
    (10, "październik", "październiku", "pazdzierniku"),
    (11, "listopad", "listopadzie", "listopadzie"),
    (12, "grudzień", "grudniu", "grudniu"),
]

# Odwzorowanie okresów ochronnych z FISH_LEGAL_SUMMARIES na miesiące.
# "months"   — miesiące objęte krajowym okresem ochronnym,
# "partial"  — miesiące, w których okres zaczyna się lub kończy w trakcie,
# "variable" — okres zależy od odcinka wody, więc listy nie mogą go przesądzać,
# "label"    — zakres pokazywany przy gatunku.
PROTECTION = {
    "szczupak": {"months": {1, 2, 3, 4}, "label": "1 stycznia–30 kwietnia"},
    "sandacz": {"months": {3, 4, 5}, "label": "1 marca–31 maja"},
    "sum": {"months": {1, 2, 3, 4, 5}, "label": "1 stycznia–31 maja"},
    "wegorz": {"months": {12, 1, 2, 3}, "label": "1 grudnia–31 marca"},
    "lipien": {"months": {3, 4, 5}, "label": "1 marca–31 maja"},
    "brzana": {"months": {1, 2, 3, 4, 5, 6}, "label": "1 stycznia–30 czerwca"},
    "swinka": {"months": {1, 2, 3, 4}, "partial": {5}, "label": "1 stycznia–15 maja"},
    "sielawa": {"months": {11, 12}, "partial": {10}, "label": "15 października–31 grudnia"},
    "sieja": {"months": {11, 12}, "partial": {10}, "label": "15 października–31 grudnia"},
    "jesiotr": {"months": set(range(1, 13)), "label": "cały rok"},
    "dorsz": {"months": set(range(1, 13)), "label": "cały rok w połowie rekreacyjnym"},
    "pstrag": {
        "variable": {9, 10, 11, 12, 1},
        "label": "1 września–31 stycznia albo 31 grudnia, zależnie od odcinka",
    },
    "mietus": {
        "variable": {12, 1, 2},
        "label": "1 grudnia–koniec lutego, z wyjątkiem wskazanego odcinka Odry",
    },
    "certa": {
        "variable": {1, 2, 3, 4, 5, 6, 9, 10, 11},
        "label": "1 września–30 listopada w dolnej Wiśle, 1 stycznia–30 czerwca w pozostałych wodach",
    },
    "troc-losos": {
        "variable": set(range(1, 13)),
        "label": "okres i dodatkowe dni zakazu zależą od odcinka",
    },
    # Gatunki bez krajowego okresu ochronnego.
    "okon": {}, "bolen": {}, "karp": {}, "lin": {}, "leszcz": {}, "jaz": {},
    "ploc": {}, "klen": {}, "amur": {}, "karas": {}, "wzdrega": {}, "ukleja": {},
    # Gatunki morskie rozliczane komunikatami GIRM.
    "sledz": {"girm": True}, "belona": {"girm": True}, "fladra": {"girm": True},
}

# Nazwy wyświetlane w listach (mianownik).
NAMES = {
    "szczupak": "Szczupak", "sandacz": "Sandacz", "okon": "Okoń", "sum": "Sum",
    "bolen": "Boleń", "wegorz": "Węgorz", "karp": "Karp", "lin": "Lin",
    "leszcz": "Leszcz", "jaz": "Jaź", "pstrag": "Pstrąg potokowy",
    "mietus": "Miętus", "lipien": "Lipień", "ploc": "Płoć", "klen": "Kleń",
    "amur": "Amur", "karas": "Karaś", "troc-losos": "Troć i łosoś",
    "sielawa": "Sielawa", "sieja": "Sieja", "brzana": "Brzana", "certa": "Certa",
    "swinka": "Świnka", "wzdrega": "Wzdręga", "ukleja": "Ukleja",
    "jesiotr": "Jesiotr", "dorsz": "Dorsz", "sledz": "Śledź", "belona": "Belona",
    "fladra": "Flądra",
}

# Część opisowa pisana per miesiąc: wprowadzenie, taktyka i odpowiedź FAQ.
NOTES = {
    1: {
        "intro": "Styczeń jest miesiącem najzimniejszej wody w roku, więc lista gatunków objętych ochroną jest długa, a metabolizm reszty ryb mocno spowolniony. To okres, w którym planowanie wyprawy zaczyna się od sprawdzenia przepisów, a nie od doboru przynęty.",
        "tactics": "Woda ma zwykle 1–4 °C, więc ryby stoją głębiej i żerują krótkimi oknami w najcieplejszej porze doby. Sprawdzają się wolne prowadzenia, drobne przynęty i długie postoje w jednym miejscu. Na wodach, gdzie lód jest bezpieczny i dozwolony przez gospodarza, sezon należy do okonia i płoci pod lodem.",
        "faq": "Zimą tempo przemiany materii ryb spada, więc żerowanie skraca się do krótkich okien w ciągu doby. Dłuższe wystawanie w jednym, dobrze rozpoznanym miejscu daje zwykle więcej niż ciągła zmiana stanowisk.",
    },
    2: {
        "intro": "Luty kończy zimowy zastój, ale przepisy wyglądają niemal tak samo jak w styczniu. Pod koniec miesiąca rosnący dzień i pierwsze odwilże potrafią ruszyć ryby białe, zanim zaczną się wiosenne okresy ochronne.",
        "tactics": "Najwięcej dzieje się przy pierwszych roztopach, gdy do wody trafia cieplejsza woda z topniejącego śniegu. Warto szukać ujść dopływów i miejsc, gdzie prąd znosi pokarm. Wciąż obowiązuje zasada drobnych przynęt i powolnego prowadzenia.",
        "faq": "Luty bywa lepszy od stycznia głównie pod koniec miesiąca, gdy dzień się wydłuża, a odwilż podnosi temperaturę wody. Przed wyjazdem sprawdź jednak, czy interesujący cię gatunek nie wchodzi już w okres ochronny.",
    },
    3: {
        "intro": "Marzec to miesiąc największej zmiany w kalendarzu przepisów: kończy się ochrona części gatunków zimowych, a zaczyna wiosenna ochrona ryb drapieżnych i łososiowatych. Zanim wyjedziesz, warto sprawdzić listę dla konkretnej wody.",
        "tactics": "Woda budzi się powoli, a ryby ciągną w płytsze, szybciej nagrzewające się strefy. Dobrze pracują miejsca z ciemnym dnem i osłoną od wiatru, gdzie woda zyskuje kilka stopni w ciągu dnia. To także czas wysokich stanów wody po roztopach, więc bezpieczeństwo nad rzeką jest ważniejsze niż zwykle.",
        "faq": "W marcu zaczynają się okresy ochronne kilku ważnych gatunków, w tym sandacza i lipienia, a kończy ochrona węgorza. Ponieważ część terminów zależy od odcinka wody, decyduje regulamin gospodarza i zezwolenie.",
    },
    4: {
        "intro": "Kwiecień to szczyt wiosennych okresów ochronnych. Wiele gatunków jest w trakcie tarła albo tuż po nim, więc lista tego, co wolno zabrać, jest w tym miesiącu wyraźnie krótsza niż latem.",
        "tactics": "Woda przekracza 8–12 °C i ryby białe zaczynają regularnie żerować. To dobry moment na spławik i lekki feeder na płoć, leszcza i wzdręgę. Ryby stoją płycej, często blisko roślinności, która dopiero zaczyna odrastać.",
        "faq": "Nie. W kwietniu trwa ochrona między innymi szczupaka, sandacza, suma, brzany i lipienia, a część gatunków ma dodatkowe ograniczenia lokalne. Zawsze sprawdzaj regulamin konkretnej wody.",
    },
    5: {
        "intro": "Maj otwiera sezon dla wielu wędkarzy: kończy się ochrona szczupaka, a w drugiej części miesiąca kolejnych gatunków. Jednocześnie część okresów trwa do końca maja, więc data wyjazdu ma tu realne znaczenie.",
        "tactics": "Woda nagrzewa się szybko, roślinność odrasta i ryby żerują intensywnie przed tarłem oraz po nim. To najlepszy miesiąc dla lina i karasia, a także mocny okres dla klenia i jazia w rzekach. Świt i wieczór dają zwykle więcej niż środek dnia.",
        "faq": "Nie w całym miesiącu. Ochrona sandacza, suma i lipienia trwa do 31 maja, a brzany do końca czerwca. Sprawdź dokładną datę i zasady lokalne przed wyjazdem.",
    },
    6: {
        "intro": "Czerwiec jest pierwszym miesiącem, w którym większość popularnych gatunków jest już poza krajowym okresem ochronnym. Zostaje kilka wyjątków oraz ograniczenia lokalne, które bywają ostrzejsze od przepisów krajowych.",
        "tactics": "Długi dzień i ciepła woda oznaczają wysoką aktywność, ale też szybkie zużycie tlenu w płytkich, zarośniętych miejscach. Najlepsze okna to wczesny świt i późny wieczór. Dobrze pracują metody spławikowe, method feeder oraz spinning przy krawędziach roślinności.",
        "faq": "Do 30 czerwca trwa ochrona brzany, a w części wód także certy. Poza tym w czerwcu decydują przede wszystkim wymiary ochronne, limity dobowe i regulamin gospodarza.",
    },
    7: {
        "intro": "Lipiec to miesiąc z najkrótszą listą krajowych okresów ochronnych, ale też z najtrudniejszymi warunkami termicznymi. Przepisy przestają być głównym ograniczeniem, a zaczyna nim być tlen i temperatura wody.",
        "tactics": "Przy wysokich temperaturach ryby schodzą głębiej albo szukają natlenionego prądu i cienia. Warto łowić nocą lub o świcie, a w upał odpuścić płytkie, zakwitnięte zatoki. Przy połowie na żywo i przy catch and release skrócony czas holu i szybkie wypuszczenie są w lipcu szczególnie ważne.",
        "faq": "Krajowo w lipcu chroniony jest przede wszystkim jesiotr, a w wodach morskich dorsz w połowie rekreacyjnym. Reszta ograniczeń wynika z wymiarów, limitów i zasad lokalnych.",
    },
    8: {
        "intro": "Sierpień pozostaje miesiącem bez większości krajowych okresów ochronnych, ale nadal obowiązują wymiary, limity dobowe i regulaminy wód. Pod koniec miesiąca woda zaczyna stygnąć i wraca aktywność drapieżników.",
        "tactics": "Pierwsza połowa miesiąca to jeszcze taktyka upalna: głębiej, nocą i w natlenionym prądzie. Od drugiej połowy sierpnia coraz lepiej pracuje spinning, bo szczupak i okoń zaczynają zbierać się przy ławicach ryb białych. To także dobry czas na suma po zmroku.",
        "faq": "Tak, poza gatunkami chronionymi całorocznie w sierpniu nie obowiązują krajowe okresy ochronne popularnych gatunków. Nadal jednak musisz zachować wymiary ochronne i limity dobowe z zezwolenia.",
    },
    9: {
        "intro": "Wrzesień otwiera jesienny sezon drapieżnika, ale jednocześnie startuje ochrona pstrąga potokowego, a w części wód certy. To miesiąc, w którym różnice między odcinkami wód są szczególnie wyraźne.",
        "tactics": "Stygnąca woda podnosi aktywność szczupaka, sandacza i okonia, a ryby zaczynają się zbierać w większe stada. Dobrze pracują większe przynęty i dłuższe przeszukiwanie toni. Dzień jest jeszcze długi, więc opłaca się rozpoznać kilka stanowisk zamiast siedzieć w jednym.",
        "faq": "Od 1 września zaczyna się ochrona pstrąga potokowego, a w dolnej Wiśle także certy. Ponieważ terminy zależą od wskazanego odcinka wody, sprawdź zezwolenie dla konkretnego łowiska.",
    },
    10: {
        "intro": "Październik to zwykle najlepszy miesiąc jesieni dla drapieżników, a zarazem początek ochrony ryb siejowatych. W połowie miesiąca lista gatunków objętych ochroną zauważalnie się wydłuża.",
        "tactics": "Woda schładza się do kilkunastu stopni i ryby żerują intensywnie przed zimą. To szczyt sezonu na sandacza i szczupaka, a także dobry czas na dużego okonia. Warto szukać krawędzi, wypłyceń przy głębi i miejsc, w których gromadzi się ryba biała.",
        "faq": "Od 15 października ochroną objęte są sielawa i sieja, a przez cały miesiąc trwa ochrona pstrąga potokowego oraz certy w części wód. Dokładny zakres wynika z zezwolenia dla danej wody.",
    },
    11: {
        "intro": "Listopad łączy jeszcze mocny sezon drapieżnika z rosnącą liczbą gatunków objętych ochroną. Warunki bywają trudne, ale to jeden z lepszych miesięcy na dużą rybę.",
        "tactics": "Woda jest zimna i przejrzysta, więc ryby stoją głębiej i reagują na wolniejsze prowadzenie. Sandacz trzyma się głębi i krawędzi, szczupak potrafi wyjść na wypłycenia w cieplejsze dni. Krótszy dzień oznacza, że okna żerowania częściej wypadają w środku dnia niż o świcie.",
        "faq": "W listopadzie chronione są między innymi sielawa, sieja i pstrąg potokowy, a w dolnej Wiśle certa do 30 listopada. Poza tym decydują wymiary ochronne i limity z zezwolenia.",
    },
    12: {
        "intro": "Grudzień zamyka rok i ponownie wydłuża listę okresów ochronnych: zaczyna się ochrona węgorza i miętusa, a nadal trwa ochrona ryb siejowatych. Sezon przechodzi w tryb zimowy.",
        "tactics": "Woda jest zimna, a ryby skupiają się w kilku sprawdzonych miejscach. Sandacz i okoń pozostają realnym celem, ale wymagają precyzyjnego prowadzenia i cierpliwości. Na wodach z bezpiecznym lodem, o ile gospodarz na to pozwala, zaczyna się sezon podlodowy.",
        "faq": "Od 1 grudnia ochroną objęty jest węgorz oraz miętus, a do 31 grudnia sielawa i sieja. Ochrona pstrąga potokowego trwa zależnie od odcinka wody.",
    },
}


def month_buckets(month):
    """Zwraca trzy rozłączne listy gatunków dla wskazanego miesiąca."""
    protected, variable, open_ = [], [], []
    for slug, rule in PROTECTION.items():
        if slug not in NAMES:
            raise ValueError(f"brak nazwy wyświetlanej dla {slug}")
        label = rule.get("label", "")
        if month in rule.get("months", set()):
            protected.append((slug, label))
        elif month in rule.get("partial", set()) or month in rule.get("variable", set()):
            variable.append((slug, label))
        elif rule.get("girm"):
            variable.append((slug, "zasady i limity ogłasza GIRM"))
        else:
            open_.append((slug, seo_inject.FISH_LEGAL_SUMMARIES[slug]))
    key = lambda item: NAMES[item[0]]
    return sorted(protected, key=key), sorted(variable, key=key), sorted(open_, key=key)


def li(slug, note):
    name = html.escape(NAMES[slug])
    return (f'<li><a href="../ryby/{slug}.html">{name}</a> — {html.escape(note)}</li>')


def build_page(month, nominative, locative, slug):
    protected, variable, open_ = month_buckets(month)
    notes = NOTES[month]
    title = f"Jakie ryby można łowić w {locative} — okresy ochronne | FishPoint"
    protected_names = ", ".join(NAMES[s].lower() for s, _ in protected) or "brak"
    desc = (
        f"Okresy ochronne w {locative}: pod ochroną krajową {protected_names}. "
        "Sprawdź, co wolno zabrać, jakie obowiązują wymiary i na co realnie łowić."
    )
    if len(desc) > 158:
        desc = (
            f"Okresy ochronne w {locative}: pełna lista gatunków pod ochroną krajową, "
            "wymiary ochronne oraz to, na co realnie łowić w tym miesiącu."
        )

    other_months = "".join(
        f'<a href="co-lowic-w-{s}.html">{n.capitalize()}</a>'
        for num, n, _l, s in MONTHS if num != month
    )

    parts = [
        '<main id="main-content">',
        '<section class="subpage-hero"><div class="container">',
        '<p class="eyebrow">Poradniki</p>',
        f'<h1>Jakie ryby można łowić w {html.escape(locative)}</h1>',
        '<!--byline:auto--><!--/byline:auto-->',
        f'<p>{html.escape(notes["intro"])}</p>',
        '</div></section>',
        '<section class="section container article-layout"><article class="article-card">',
        '<!--article-visual:auto--><!--/article-visual:auto-->',
        '<!--tldr:auto--><!--/tldr:auto--><!--toc:auto--><!--/toc:auto-->',
    ]

    parts.append(
        f'<h2 id="pod-ochrona-krajowa">Pod ochroną krajową w {html.escape(locative)}</h2>'
    )
    if protected:
        parts.append(
            "<p>Tych gatunków nie wolno zabrać z wody w tym miesiącu na podstawie "
            "przepisów krajowych. Złowioną rybę wypuść niezwłocznie, z jak najmniejszym "
            "uszczerbkiem.</p>"
        )
        parts.append("<ul>" + "".join(li(s, n) for s, n in protected) + "</ul>")
    else:
        parts.append(
            "<p>W tym miesiącu żaden z opisywanych gatunków nie jest objęty krajowym "
            "okresem ochronnym przez cały miesiąc. Nadal obowiązują jednak wymiary "
            "ochronne, limity dobowe i zasady lokalne.</p>"
        )

    parts.append('<h2 id="zalezne-od-odcinka">Ochrona zależna od odcinka wody lub daty</h2>')
    parts.append(
        "<p>Przy tych gatunkach sam miesiąc nie wystarcza do rozstrzygnięcia. Okres "
        "ochronny zaczyna się lub kończy w trakcie miesiąca albo zależy od wskazanego "
        "odcinka wody, więc decyduje treść rozporządzenia i zezwolenia dla konkretnego "
        "łowiska.</p>"
    )
    parts.append(
        "<ul>" + "".join(li(s, n) for s, n in variable) + "</ul>" if variable
        else "<p>W tym miesiącu żaden gatunek nie wpada w tę kategorię.</p>"
    )

    parts.append(
        f'<h2 id="poza-okresem-ochronnym">Poza okresem ochronnym w {html.escape(locative)}</h2>'
    )
    parts.append(
        "<p>Te gatunki nie są w tym miesiącu objęte krajowym okresem ochronnym. Część z "
        "nich ma jednak okres ochronny w innych miesiącach, dlatego przy każdym podajemy "
        "pełną treść przepisu krajowego. Brak okresu nie oznacza zgody na zabranie ryby: "
        "nadal obowiązują wymiar ochronny, limit dobowy oraz regulamin gospodarza wody, "
        "który bywa ostrzejszy od przepisu krajowego.</p>"
    )
    parts.append("<ul>" + "".join(li(s, n) for s, n in open_) + "</ul>")

    parts.append(
        f'<h2 id="na-co-lowic">Na co realnie łowić w {html.escape(locative)}</h2>'
        f'<p>{html.escape(notes["tactics"])}</p>'
        '<p>Szczegółową sezonowość pojedynczych gatunków znajdziesz w '
        '<a href="kalendarz-bran.html">kalendarzu brań</a>, a pełną tabelę wymiarów i '
        'okresów w <a href="../narzedzia/okresy-ochronne.html">narzędziu FishPoint</a>.</p>'
    )

    parts.append(
        '<section class="info-block" aria-label="Zanim pojedziesz">'
        '<h2 id="zanim-pojedziesz">Zanim pojedziesz nad wodę</h2>'
        '<p>Ta strona porządkuje przepisy krajowe. Nie zastępuje zezwolenia ani '
        'regulaminu gospodarza wody, a te mogą wprowadzać ostrzejszy wymiar, dodatkowy '
        'okres ochronny, niższy limit dobowy lub zakaz zabierania ryb. Jeżeli pierwszy '
        'lub ostatni dzień okresu ochronnego przypada w dzień ustawowo wolny od pracy, '
        'okres skraca się o ten dzień (§ 7 ust. 2); wyjątkiem jest całoroczna ochrona '
        'jesiotra.</p></section>'
    )

    parts.append('<h2 id="faq-najczestsze-pytania">FAQ — najczęstsze pytania</h2>')
    parts.append(
        f'<section class="info-block"><h3>Czy w {html.escape(locative)} można zabrać '
        f'każdą złowioną rybę?</h3><p>{html.escape(notes["faq"])}</p></section>'
    )
    parts.append(
        '<section class="info-block"><h3>Skąd pochodzą te okresy ochronne?</h3>'
        '<p>Z rozporządzenia Ministra Rolnictwa i Rozwoju Wsi w sprawie połowu ryb oraz '
        'warunków chowu, hodowli i połowu innych organizmów żyjących w wodzie '
        '(Dz.U. 2023 poz. 1373, § 6–8). Wartości lokalne mogą być ostrzejsze i wynikają '
        'z zezwolenia oraz regulaminu gospodarza wody.</p></section>'
    )
    parts.append(
        '<section class="info-block"><h3>Co zrobić po złowieniu ryby pod ochroną?</h3>'
        '<p>Wypuść ją niezwłocznie, najlepiej bez wyjmowania z wody, z mokrymi dłońmi i '
        'przy użyciu podbieraka o miękkiej siatce. Jeżeli nie masz pewności co do '
        'gatunku lub wymiaru, potraktuj rybę jak chronioną.</p></section>'
    )

    parts.append(
        '<div class="source-box"><h3>Źródła i zakres</h3>'
        '<p>Listy gatunków wynikają z '
        '<a href="https://eli.gov.pl/api/acts/DU/2023/1373/text.html" rel="noopener external" '
        'target="_blank">Dz.U. 2023 poz. 1373, § 6–8</a>. Zasady połowu morskiego ogłasza '
        '<a href="https://www.gov.pl/web/girm/informacje-ogolne-nt-rybolowstwa-rekreacyjnego" '
        'rel="noopener external" target="_blank">Główny Inspektorat Rybołówstwa Morskiego</a>. '
        'Strona porządkuje przepisy krajowe i nie zastępuje zezwolenia ani regulaminu '
        'gospodarza wody.</p></div>'
    )

    parts.append('<!--related:auto--><!--/related:auto--></article>')
    parts.append(
        '<aside class="side-nav"><h3>Miesiąc po miesiącu</h3>'
        + other_months
        + '<a href="kalendarz-bran.html">Kalendarz brań</a>'
        + '<a href="../narzedzia/okresy-ochronne.html">Tabela okresów i wymiarów</a>'
        + '</aside></section></main>'
    )

    footer = (
        '<footer class="footer"><div class="container footer-grid">'
        '<p class="footer-author">Autor treści: <span rel="author">Maciej Baniewicz</span></p>'
        '<p>© 2026 FishPoint.</p><p>Poradniki wędkarskie</p>'
        '<p class="footer-legal"><a href="../zgodnie-z-zasadami.html">Przepisy i dokumenty</a> · '
        '<a href="../slownik.html">Słownik</a> · '
        '<a href="../korekty.html">Rejestr korekt</a> · '
        '<a href="https://fish-point.pl/o-autorze.html">O autorze</a></p>'
        '</div></footer><script defer src="../js/main.js"></script></body></html>'
    )

    head = (
        '<!doctype html>\n<html lang="pl">\n<head>\n'
        '  <!--content-meta: published={published}; modified={modified}-->\n'
        # Dwanaście stron miesięcznych powstaje z jednej tabeli okresów ochronnych
        # i jest w ~74% wzajemnie podobnych. Google indeksował z nich tylko jedną
        # („wykryta, obecnie niezindeksowana”), więc nie zgłaszamy ich do indeksu —
        # dla czytelnika pozostają dostępne i linkowane z huba działu.
        '  <meta name="robots" content="noindex, follow" />\n'
        '  <meta charset="utf-8" />\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f'  <title>{html.escape(title)}</title>\n'
        f'  <meta name="description" content="{html.escape(desc, quote=True)}" />\n'
        '  <link rel="stylesheet" href="../css/style.css" />\n'
        '</head>\n<body>\n'
        '<a class="skip-link" href="#main-content">Przejdź do treści</a>'
        '<header class="site-header"></header>\n'
    )
    return head + "".join(parts) + footer


CONTENT_META_RE = re.compile(
    r"<!--content-meta:\s*published=(\d{4}-\d{2}-\d{2});\s*modified=(\d{4}-\d{2}-\d{2})-->")


def main():
    if sorted(PROTECTION) != sorted(seo_inject.FISH_LEGAL_SUMMARIES):
        missing = set(seo_inject.FISH_LEGAL_SUMMARIES) - set(PROTECTION)
        extra = set(PROTECTION) - set(seo_inject.FISH_LEGAL_SUMMARIES)
        raise SystemExit(
            f"rejestr miesięczny rozjechał się z FISH_LEGAL_SUMMARIES; brakuje: "
            f"{sorted(missing)}, nadmiarowe: {sorted(extra)}")

    today = os.environ.get("FISHPOINT_BUILD_DATE", "2026-08-01")
    written = 0
    for number, nominative, locative, slug in MONTHS:
        path = os.path.join(OUT_DIR, f"co-lowic-w-{slug}.html")
        published, modified = today, today
        if os.path.exists(path):
            found = CONTENT_META_RE.search(open(path, encoding="utf-8").read())
            if found:
                published = found.group(1)
        page = build_page(number, nominative, locative, slug)
        page = page.replace("{published}", published).replace("{modified}", modified)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page)
        written += 1
        print(f"zapisano poradniki/co-lowic-w-{slug}.html")
    print(f"Strony miesięczne: {written}")


if __name__ == "__main__":
    main()
