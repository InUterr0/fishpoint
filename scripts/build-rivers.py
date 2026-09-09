#!/usr/bin/env python3
"""Buduje dział „Rzeki" z publicznych danych hydrologicznych IMGW-PIB.

Dlaczego statycznie, skoro `narzedzia/stany-wod.html` już pyta IMGW z
przeglądarki: tamto narzędzie renderuje tabelę dopiero po wyborze
województwa, więc dla robota — i dla czytelnika przed pierwszym kliknięciem
— strona jest pusta. Odczyty z 913 wodowskazów nie istnieją w HTML, nie
trafiają do indeksu i nie odpowiadają na pytanie „jaki jest stan wody na
Drawie". Ten skrypt zapisuje je do dokumentu.

Zakres jest celowo węższy niż dane. Stronę dostają rzeki z co najmniej
czterema wodowskazami: przy mniejszej liczbie punktów nie da się policzyć
spadku ani opisać biegu, a strona byłaby powtórzeniem jednego wiersza
tabeli. Pozostałe rzeki są widoczne na stronie działu.

Uruchamiać PRZED seo_inject.py — generator dokłada do gotowego szkieletu
nawigację, blok SEO, podpis redakcyjny i newsletter.
"""
from __future__ import annotations

import datetime
import html
import math
import statistics
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "dane" / "imgw-hydro.json"
BOUNDARIES = ROOT / "dane" / "wojewodztwa.geojson"
OUT_DIR = ROOT / "rzeki"
API = "https://danepubliczne.imgw.pl/api/data/hydro/"

# IMGW trzyma przy każdym polu datę JEGO pomiaru — przepływ albo temperatura
# potrafią pochodzić sprzed miesięcy. Wartość bez świeżej daty nie opisuje
# dzisiejszej wody, więc do dokumentu nie trafia. Trzy doby to ten sam próg,
# którego używa narzędzie „Stany wód na żywo".
FRESH_DAYS = 3

# Zbiorniki i wody przybrzeżne mają w API własne wpisy, ale „bieg rzeki"
# i spadek nie mają dla nich sensu — dział opisuje rzeki.
NOT_RIVERS = {
    "Bałtyk", "Morze Bałtyckie", "Zalew Wiślany", "Zalew Szczeciński",
    "Jezioro", "Kanał Żerański",
}

MIN_STATIONS = 4

LEAD_IMAGE = "/assets/img/tematy/rozlewisko-spinning.jpg"

SMALL_WORDS = {"nad", "pod", "przy", "na", "w", "we", "u", "do", "z", "ze", "i", "k"}


def log(*args) -> None:
    print("[rzeki]", *args)


# --- dane ------------------------------------------------------------------

def fetch_stations() -> tuple[list[dict], bool]:
    """Zwraca (stacje, czy_ze_swiezego_pobrania).

    Awaria IMGW nie może wywracać wdrożenia całego serwisu, więc przy błędzie
    wracamy do ostatniego zapisanego zrzutu. Strona i tak podaje przy każdym
    odczycie jego własną datę pomiaru, więc czytelnik widzi wiek danych.
    """
    try:
        request = urllib.request.Request(API, headers={"User-Agent": "FishPoint/1.0 (+https://fish-point.pl)"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.load(response)
        if not isinstance(data, list) or len(data) < 100:
            raise ValueError(f"nieoczekiwana odpowiedź API: {type(data).__name__}, {len(data)} pozycji")
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"pobrano {len(data)} stacji z IMGW")
        return data, True
    except Exception as exc:  # noqa: BLE001 - każdy błąd sieci ma kończyć się fallbackiem
        if not SNAPSHOT.exists():
            raise SystemExit(f"[rzeki] IMGW niedostępne i brak zrzutu {SNAPSHOT}: {exc}")
        log(f"IMGW niedostępne ({exc}); używam zrzutu {SNAPSHOT.name}")
        return json.loads(SNAPSHOT.read_text(encoding="utf-8")), False


def as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_stamp(value) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value).strip().replace(" ", "T"))
    except ValueError:
        return None


def is_fresh(value, now: datetime.datetime) -> bool:
    stamp = parse_stamp(value)
    if stamp is None:
        return False
    age = now - stamp
    return datetime.timedelta(hours=-6) <= age <= datetime.timedelta(days=FRESH_DAYS)


# Sortowanie polskie: domyślny porządek Pythona idzie po punktach kodowych,
# więc „śląskie" ląduje za „zachodniopomorskim", a „łódzkie" za „wielkopolskim".
PL_ORDER = {"ą": "a~", "ć": "c~", "ę": "e~", "ł": "l~", "ń": "n~",
            "ó": "o~", "ś": "s~", "ź": "z~", "ż": "z~~"}


def pl_key(text: str) -> str:
    return "".join(PL_ORDER.get(ch, ch) for ch in text.lower())


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text


def _clean_voivodeship(value) -> str:
    """Pole IMGW bywa puste albo zawiera sam myślnik (stacja Słubice)."""
    value = (value or "").strip()
    return "" if value in ("", "-", "—") else value


def tidy_name(name: str) -> str:
    """Poprawia zapis nazw stacji, nie zmieniając ich brzmienia.

    IMGW miesza wielkość liter w drugim członie („Drawsko pomorskie",
    „Stare drawsko"). Podnosimy pierwszą literę członu, jeśli cały człon jest
    zapisany małymi literami i nie jest przyimkiem — nie tłumaczymy i nie
    skracamy nazw, żeby dało się je zestawić z wykazem wodowskazów.
    """
    parts = name.split()
    out = []
    for index, part in enumerate(parts):
        stripped = part.strip("-.,")
        if index and stripped.islower() and stripped.lower() not in SMALL_WORDS:
            part = part[:1].upper() + part[1:]
        out.append(part)
    return " ".join(out)



def haversine_km(first: dict, second: dict) -> float | None:
    """Odległość w linii prostej między dwiema stacjami."""
    if None in (first["lat"], first["lon"], second["lat"], second["lon"]):
        return None
    radius = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, (first["lat"], first["lon"], second["lat"], second["lon"]))
    inner = (math.sin((lat2 - lat1) / 2) ** 2
             + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * radius * math.asin(math.sqrt(inner))



# --- województwo z współrzędnych ------------------------------------------
# Pole `wojewodztwo` w API IMGW jest puste dla 314 z 913 stacji, a w kilku
# przypadkach błędne (Drawiny leżą w lubuskiem, nie w wielkopolskiem). Skoro
# każda stacja ma współrzędne, region wyznaczamy z granic województw i
# zestawiamy z polem IMGW tylko wtedy, gdy punkt wypadnie poza poligonami.
# Kontrola na pełnym wykazie: 593 zgodne, 3 rozbieżne (wszystkie przygraniczne).

def load_boundaries() -> list[tuple[str, list, tuple[float, float, float, float]]]:
    if not BOUNDARIES.exists():
        log(f"brak {BOUNDARIES.name} — województwa wezmę z pola IMGW")
        return []
    data = json.loads(BOUNDARIES.read_text(encoding="utf-8"))
    out = []
    for feature in data["features"]:
        geometry = feature["geometry"]
        polygons = ([geometry["coordinates"]] if geometry["type"] == "Polygon"
                    else geometry["coordinates"])
        for polygon in polygons:
            outer = polygon[0]
            lons = [point[0] for point in outer]
            lats = [point[1] for point in outer]
            out.append((feature["properties"]["nazwa"], outer,
                        (min(lons), min(lats), max(lons), max(lats))))
    return out


BOUNDARY_RINGS = load_boundaries()


def _point_in_ring(lon: float, lat: float, ring: list) -> bool:
    inside = False
    count = len(ring)
    previous = count - 1
    for current in range(count):
        lon_i, lat_i = ring[current][0], ring[current][1]
        lon_j, lat_j = ring[previous][0], ring[previous][1]
        if (lat_i > lat) != (lat_j > lat) and \
                lon < (lon_j - lon_i) * (lat - lat_i) / (lat_j - lat_i) + lon_i:
            inside = not inside
        previous = current
    return inside


def voivodeship_at(lat: float | None, lon: float | None) -> str | None:
    if lat is None or lon is None:
        return None
    for name, ring, (min_lon, min_lat, max_lon, max_lat) in BOUNDARY_RINGS:
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat and _point_in_ring(lon, lat, ring):
            return name
    return None


# --- model rzeki -----------------------------------------------------------

class River:
    def __init__(self, name: str, stations: list[dict], now: datetime.datetime):
        self.name = name
        self.slug = slugify(name)
        self.locative = name  # nadpisywane pewnymi formami z tabel LOCATIVE/GENITIVE
        self.genitive = name
        self.now = now
        rows = []
        for raw in stations:
            lat, lon = as_float(raw.get("lat")), as_float(raw.get("lon"))
            # Wykaz IMGW zawiera stacje ze współrzędnymi 0,0 (m.in. drugi wpis
            # „Nowa sól" na Odrze). Punkt na Zatoce Gwinejskiej wywróciłby i test
            # spójności biegu, i przypisanie województwa.
            if lat == 0 and lon == 0:
                lat = lon = None
            km = as_float(raw.get("kilometr_biegu_rzeki"))
            level = as_float(raw.get("stan_wody"))
            warn = as_float(raw.get("stan_ostrzegawczy"))
            alarm = as_float(raw.get("stan_alarmowy"))
            temp = as_float(raw.get("temperatura_wody"))
            rows.append({
                "station": tidy_name(raw.get("stacja") or "—"),
                "voivodeship": voivodeship_at(lat, lon) or _clean_voivodeship(raw.get("wojewodztwo")),
                "km": km,
                "lat": lat,
                "lon": lon,
                "zero": as_float(raw.get("rzedna_zerawodowskazu")),
                "level": level if is_fresh(raw.get("stan_wody_data_pomiaru"), now) else None,
                "level_stamp": raw.get("stan_wody_data_pomiaru"),
                "warn": warn,
                "alarm": alarm,
                "temp": temp if is_fresh(raw.get("temperatura_wody_data_pomiaru"), now) else None,
                "temp_stamp": raw.get("temperatura_wody_data_pomiaru"),
                "flow": as_float(raw.get("przeplyw")) if is_fresh(raw.get("przeplyw_data"), now) else None,
                "year": raw.get("rok_zalozenia_stacji") or None,
                "ice": (raw.get("zjawisko_lodowe") not in (None, "", "0")
                        and is_fresh(raw.get("zjawisko_lodowe_data_pomiaru"), now)),
            })
        # Od ujścia w górę biegu: tak czyta się rzekę na mapie i tak rosną
        # kilometraż oraz rzędna zera wodowskazu.
        rows.sort(key=lambda row: (row["km"] is None, row["km"] or 0))
        self.rows = rows

    # -- pochodne
    @property
    def is_single_watercourse(self) -> bool:
        """Czy wszystkie wodowskazy leżą na jednym cieku.

        W wykazie IMGW nazwa rzeki nie jest identyfikatorem: „Czarna",
        „Biała", „Kamienna", „Bystrzyca" i „Piława" to po kilka odrębnych
        rzek w różnych częściach Polski, a kilometraż każdej liczy się od jej
        własnego ujścia. Zlepienie ich w jedną stronę dałoby bezsensowny
        spadek odcinka i tabelę udającą jeden ciek.

        Sprawdzamy więc, czy sąsiednie wodowskazy dają się pogodzić z biegiem
        jednej rzeki: odległość w linii prostej nie może przekraczać różnicy
        kilometrażu z zapasem na meandry (mnożnik 1,6) i na krótkie odcinki
        (15 km). Rzeki jednorodne mieszczą się w tym progu z ogromnym marginesem
        (najgorsza — Wisła — na poziomie 0,51), homonimy przekraczają go
        wielokrotnie (od 6,7 wzwyż), więc próg nie jest tu granicą sporną.
        """
        points = [row for row in self.rows
                  if row["km"] is not None and row["lat"] is not None and row["lon"] is not None]
        if len(points) < 2:
            return True
        points.sort(key=lambda row: row["km"])
        for lower, upper in zip(points, points[1:]):
            straight = haversine_km(lower, upper)
            if straight is None:
                continue
            if straight > 1.6 * (upper["km"] - lower["km"]) + 15:
                return False
        return True

    @property
    def voivodeships(self) -> list[str]:
        return sorted({row["voivodeship"] for row in self.rows if row["voivodeship"]}, key=pl_key)

    @property
    def measured(self) -> list[dict]:
        return [row for row in self.rows if row["level"] is not None]

    @property
    def span_km(self) -> float | None:
        kms = [row["km"] for row in self.rows if row["km"] is not None]
        return round(max(kms) - min(kms), 1) if len(kms) >= 2 else None

    @property
    def drop(self) -> float | None:
        """Różnica rzędnych zer łat między skrajnymi wodowskazami, w metrach."""
        pts = [(row["km"], row["zero"]) for row in self.rows
               if row["km"] is not None and row["zero"] is not None]
        if len(pts) < 2:
            return None
        pts.sort()
        return round(pts[-1][1] - pts[0][1], 1)

    @property
    def gradient(self) -> float | None:
        """Mediana spadków między sąsiednimi wodowskazami, w metrach na kilometr.

        Świadomie NIE średnia ze skrajnych stacji. Wisła ma źródła w Beskidzie
        Śląskim, więc licząc od Wisły Czarnej do ujścia dostaje 0,51 m/km i
        wychodzi na rzekę „podgórską" — opis fałszywy dla tysiąca kilometrów
        nizinnego biegu, na którym się ją łowi. Mediana odcinków daje 0,26 m/km
        i opisuje rzekę taką, jaka jest na większości długości.
        """
        pts = sorted((row["km"], row["zero"]) for row in self.rows
                     if row["km"] is not None and row["zero"] is not None)
        segments = [(upper[1] - lower[1]) / (upper[0] - lower[0])
                    for lower, upper in zip(pts, pts[1:]) if upper[0] > lower[0]]
        if not segments:
            return None
        return round(statistics.median(segments), 2)

    @property
    def character(self) -> tuple[str, str]:
        """(etykieta, zdanie) — wyłącznie z policzonego spadku."""
        gradient = self.gradient
        if gradient is None:
            return ("nieokreślony", "danych o rzędnych zer wodowskazów jest za mało, żeby policzyć spadek odcinka.")
        if gradient >= 2:
            return ("górski", "nurt jest szybki, a poziom reaguje na opady w godzinach, nie w dniach.")
        if gradient >= 0.5:
            return ("podgórski", "nurt bywa wyraźny, a wezbrania schodzą szybciej niż na wielkich rzekach nizinnych.")
        return ("nizinny", "nurt jest wolniejszy, a fala wezbraniowa dłuższa niż na wodach o większym spadku.")

    @property
    def above_warning(self) -> list[dict]:
        return [row for row in self.measured
                if row["warn"] is not None and row["level"] >= row["warn"]]

    @property
    def above_alarm(self) -> list[dict]:
        return [row for row in self.measured
                if row["alarm"] is not None and row["level"] >= row["alarm"]]

    @property
    def temps(self) -> list[dict]:
        return [row for row in self.rows if row["temp"] is not None]

    @property
    def newest_stamp(self) -> str | None:
        stamps = [parse_stamp(row["level_stamp"]) for row in self.measured]
        stamps = [s for s in stamps if s]
        return max(stamps).strftime("%d.%m.%Y, godz. %H:%M") if stamps else None


# --- teksty ----------------------------------------------------------------

MONTHS = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
          "sierpnia", "września", "października", "listopada", "grudnia")


def pl_date(day: datetime.date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def plural(count: int, one: str, few: str, many: str) -> str:
    if count == 1:
        return one
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return few
    return many


def fmt(value: float | None, unit: str = "") -> str:
    if value is None:
        return "—"
    text = f"{value:g}".replace(".", ",")
    return f"{text}{unit}"


# Miejscownik nazw województw — w API IMGW występują w mianowniku.
VOIVODESHIP_LOCATIVE = {
    "dolnośląskie": "dolnośląskim", "kujawsko-pomorskie": "kujawsko-pomorskim",
    "lubelskie": "lubelskim", "lubuskie": "lubuskim", "łódzkie": "łódzkim",
    "małopolskie": "małopolskim", "mazowieckie": "mazowieckim", "opolskie": "opolskim",
    "podkarpackie": "podkarpackim", "podlaskie": "podlaskim", "pomorskie": "pomorskim",
    "śląskie": "śląskim", "świętokrzyskie": "świętokrzyskim",
    "warmińsko-mazurskie": "warmińsko-mazurskim", "wielkopolskie": "wielkopolskim",
    "zachodniopomorskie": "zachodniopomorskim",
}


def voivodeships_locative(names: list[str]) -> str:
    return join_pl([VOIVODESHIP_LOCATIVE.get(name, name) for name in names])


def join_pl(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " i " + items[-1]


def reading_sentence(river: River) -> str:
    """Stan wobec progów ostrzegawczych — z nazwami stacji, więc zdanie
    opisuje tę rzekę, a nie „rzekę w ogóle"."""
    measured = river.measured
    if not measured:
        return (f"Żaden z {len(river.rows)} wodowskazów na {river.locative} nie podał stanu wody w ostatnich "
                f"{FRESH_DAYS} dobach, więc dzisiejszego poziomu z danych IMGW odczytać się nie da.")
    alarm = river.above_alarm
    warn = [row for row in river.above_warning if row not in alarm]
    if alarm or warn:
        parts = []
        if alarm:
            parts.append("stan alarmowy na " + join_pl([row["station"] for row in alarm]))
        if warn:
            parts.append("stan ostrzegawczy na " + join_pl([row["station"] for row in warn]))
        return (f"Ostatnie odczyty na {river.locative} pokazują przekroczony " + ", a także ".join(parts)
                + f". Pozostałe wodowskazy z tej {plural(len(measured), 'grupy', 'grupy', 'grupy')} "
                  f"({len(measured)} z {len(river.rows)} z aktualnym pomiarem) mieszczą się poniżej progów.")
    with_warn = [row for row in measured if row["warn"] is not None]
    if with_warn:
        closest = min(with_warn, key=lambda row: row["warn"] - row["level"])
        margin = round(closest["warn"] - closest["level"])
        highest = max(measured, key=lambda row: row["level"])
        tail = ""
        if highest is not closest:
            tail = (f" Najwyższy odczyt na odcinku ma {highest['station']} — {fmt(highest['level'], ' cm')} "
                    f"nad zerem swojej łaty.")
        return (f"Na {river.locative} żaden z {len(measured)} czynnych wodowskazów nie sięga stanu ostrzegawczego. "
                f"Najbliżej progu jest {closest['station']}: {fmt(closest['level'], ' cm')}, czyli {fmt(margin)} cm "
                f"pod progiem.{tail}")
    highest = max(measured, key=lambda row: row["level"])
    lowest = min(measured, key=lambda row: row["level"])
    return (f"IMGW nie wyznaczyło dla wodowskazów na {river.locative} progów ostrzegawczych, więc odczyty mają sens "
            f"wyłącznie w porównaniu z historią tej samej stacji. Dziś rozpiętość sięga od {fmt(lowest['level'], ' cm')} "
            f"({lowest['station']}) do {fmt(highest['level'], ' cm')} ({highest['station']}).")


def course_sentences(river: River) -> list[str]:
    """Bieg rzeki w liczbach — każde zdanie niesie wartość tylko dla tej rzeki."""
    out = []
    rows = [row for row in river.rows if row["km"] is not None]
    if len(rows) >= 2:
        lower, upper = rows[0], rows[-1]
        out.append(
            f"Pomiary obejmują {fmt(river.span_km)} km biegu — od stacji {lower['station']} "
            f"({fmt(lower['km'])} km od ujścia) po {upper['station']} na {fmt(upper['km'])} kilometrze."
        )
    voivodeships = river.voivodeships
    if voivodeships:
        out.append(
            f"Wodowskazy leżą w {plural(len(voivodeships), 'województwie', 'województwach', 'województwach')} "
            f"{voivodeships_locative(voivodeships)} — to również obszar, na którym szukać trzeba właściwego "
            f"gospodarza obwodu i zezwolenia na tę wodę."
        )
    gradient = river.gradient
    label, explanation = river.character
    if gradient is not None:
        out.append(
            f"Na {fmt(river.span_km)} km objętych pomiarami zero łaty opada łącznie o {fmt(river.drop)} m. "
            f"Typowy odcinek między sąsiednimi stacjami traci {fmt(gradient)} m na kilometr i to ta wartość, "
            f"odporna na krótki stromy odcinek źródłowy, daje charakter <strong>{label}</strong> — "
            f"{explanation}"
        )
    else:
        out.append(explanation)
    flows = [row for row in river.rows if row["flow"] is not None]
    if len(flows) >= 2:
        low = min(flows, key=lambda row: row["flow"])
        high = max(flows, key=lambda row: row["flow"])
        out.append(
            f"Przepływ mierzy {len(flows)} {plural(len(flows), 'stacja', 'stacje', 'stacji')}: od "
            f"{fmt(low['flow'], ' m³/s')} ({low['station']}) do {fmt(high['flow'], ' m³/s')} przy stacji "
            f"{high['station']} — różnicę robią dopływy oraz to, czy stacja stoi powyżej, czy poniżej "
            f"zbiornika albo jazu."
        )
    elif flows:
        out.append(
            f"Przepływ raportuje jedna stacja — {flows[0]['station']}, {fmt(flows[0]['flow'], ' m³/s')} "
            "w ostatnim pomiarze."
        )
    years = sorted((int(row["year"]), row["station"]) for row in river.rows if row["year"])
    if years:
        oldest_year, oldest_station = years[0]
        out.append(
            f"Wodowskaz {oldest_station} mierzy poziom od {oldest_year} roku, a najmłodsza stacja "
            f"({years[-1][1]}) od {years[-1][0]} — {years[-1][0] - oldest_year} "
            f"{plural(years[-1][0] - oldest_year, 'rok', 'lata', 'lat')} różnicy w długości serii pomiarowej "
            f"na jednej rzece."
        )
    return out


def temperature_sentence(river: River) -> str:
    temps = river.temps
    if not temps:
        return (f"Żaden wodowskaz na {river.locative} nie raportuje temperatury wody — mierzy ją tylko część stacji "
                "hydrologicznych w kraju, więc nie jest to dzisiejsza luka w danych.")
    values = [row["temp"] for row in temps]
    coldest = min(temps, key=lambda row: row["temp"])
    warmest = max(temps, key=lambda row: row["temp"])
    where = ", ".join(f"{row['station']} {fmt(row['temp'], ' °C')}" for row in temps[:4])
    if len(temps) == 1:
        return (f"Temperaturę wody podaje na {river.locative} jedna stacja: {where}. Jeden punkt nie opisuje całego "
                "biegu, ale wystarczy, żeby śledzić kierunek zmian z dnia na dzień.")
    return (f"Temperaturę wody {'mierzą' if 2 <= len(temps) % 10 <= 4 and not 12 <= len(temps) % 100 <= 14 else 'mierzy'} "
            f"tu {len(temps)} {plural(len(temps), 'stacja', 'stacje', 'stacji')}: najzimniej jest przy stacji "
            f"{coldest['station']} ({fmt(coldest['temp'], ' °C')}), najcieplej przy {warmest['station']} "
            f"({fmt(warmest['temp'], ' °C')}). Rozrzut {fmt(round(warmest['temp'] - coldest['temp'], 1), ' °C')} "
            f"między stacjami mówi więcej niż pojedyncza liczba.")


def angling_sentences(river: River) -> list[str]:
    """Konsekwencje dla wędkarza — wyprowadzone z policzonego charakteru rzeki."""
    label, _ = river.character
    gradient = river.gradient
    out = []
    if label == "górski":
        out.append(
            f"Przy spadku {fmt(gradient)} m/km woda na {river.locative} reaguje na opady w godzinach: poziom potrafi "
            "podskoczyć i opaść w ciągu jednego dnia, więc odczyt sprzed doby bywa już nieaktualny, a brodzenie "
            "wymaga sprawdzenia stanu tuż przed wyjściem."
        )
    elif label == "podgórski":
        out.append(
            f"Przy spadku {fmt(gradient)} m/km {river.name} leży pomiędzy wodą górską a nizinną: wezbranie "
            f"schodzi szybciej niż na wielkich rzekach nizinnych, ale wolniej niż w potoku, więc po większym "
            f"deszczu warto dać rzece dobę na sklarowanie."
        )
    elif label == "nizinny":
        out.append(
            f"Mały spadek ({fmt(gradient)} m/km) oznacza na {river.locative} długą falę wezbraniową: poziom rośnie "
            "i opada dniami, a nie godzinami. Odczyt sprzed doby zwykle nadal opisuje warunki, które zastaniesz."
        )
    else:
        out.append(
            f"Bez policzonego spadku o tempie zmian na {river.locative} rozstrzyga wyłącznie porównanie kolejnych "
            "odczytów tej samej stacji."
        )
    if river.above_warning:
        out.append(
            f"Przy progu przekroczonym na {len(river.above_warning)} z {len(river.rows)} wodowskazów "
            f"{river.locative} pierwszą decyzją jest wybór dojścia, nie przynęty: podmyty brzeg i zalane łachy "
            f"są realnym zagrożeniem, a zakaz wstępu na wały wydaje gmina lub zarządca wód, nie IMGW."
        )
    else:
        lowest = min(river.measured, key=lambda row: row["level"]) if river.measured else None
        if lowest:
            out.append(
                f"Poniżej progów o wyborze miejsca decyduje raczej struktura dna niż sam poziom; najniżej stoi dziś "
                f"woda przy stacji {lowest['station']} ({fmt(lowest['level'], ' cm')}), a odsłonięte przy takim "
                f"stanie łachy warto zapamiętać na resztę sezonu."
            )
        else:
            out.append(
                f"Bez świeżych odczytów na {river.locative} o wyborze stanowiska decyduje obserwacja na miejscu."
            )
    out.append(temperature_sentence(river))
    return out


def faq_pairs(river: River) -> list[tuple[str, str]]:
    stamp = river.newest_stamp
    measured = river.measured
    rows = [row for row in river.rows if row["km"] is not None]
    span = f"{fmt(river.span_km)} km biegu" if river.span_km else "całym opomiarowanym odcinku"
    pairs = [
        (f"Jaki jest dziś stan wody na {river.locative}?",
         (f"Tabela wyżej zbiera {len(river.rows)} {plural(len(river.rows), 'wodowskaz', 'wodowskazy', 'wodowskazów')} "
          f"IMGW rozstawionych na {span}"
          + (f"; {len(measured)} z nich ma pomiar z ostatnich {FRESH_DAYS} dób, a najnowszy pochodzi z {stamp}. "
             if measured and stamp else ". ")
          + f"Każdy z {len(river.rows)} wierszy ma własną godzinę pomiaru, bo stacje raportują niezależnie.")),
        (f"Czemu odczyty poszczególnych stacji na {river.locative} tak się różnią?",
         ("Stan wody to wysokość lustra nad zerem konkretnej łaty, a każda łata ma własne zero na innej rzędnej"
          + (f" — na tym odcinku różnica rzędnych skrajnych stacji sięga {fmt(round(river.drop or 0))} m. "
             if river.drop else ". ")
          + f"Zestawienie dwóch stacji na {river.locative} nie mówi więc nic o tym, gdzie jest głębiej — "
            f"porównuj jedną łatę w czasie.")),
        (f"Czy wysoka woda na {river.locative} oznacza, że nie warto jechać?",
         (f"Z samego poziomu to nie wynika. Przybierająca woda niesie zawiesinę, ale spycha rybę pod brzeg "
          f"i w miejsca bez nurtu. Odczyt z {len(river.rows)} wodowskazów {river.genitive} opisuje warunki "
          f"i bezpieczeństwo dojścia, a nie szanse na branie.")),
        (f"Gdzie sprawdzić, kto gospodaruje wodami na {river.locative}?",
         (f"Odcinek objęty pomiarami leży w {plural(len(river.voivodeships), 'województwie', 'województwach', 'województwach')} "
          f"{voivodeships_locative(river.voivodeships)}, ale granice obwodów rybackich nie pokrywają się z granicami województw — "
          f"na {river.locative} jeden okręg może gospodarować kilkoma obwodami. Zezwolenie i wykaz wód sprawdzaj "
          f"u gospodarza obwodu, a okresy ochronne w naszym narzędziu."))
        if river.voivodeships else
        (f"Czy dane o {river.locative} zastępują sprawdzenie przepisów?",
         ("Nie. Stan wody nie mówi nic o okresach ochronnych, wymiarach ani o tym, kto gospodaruje wodą.")),
    ]
    return pairs


# --- HTML ------------------------------------------------------------------

def esc(value: str) -> str:
    return html.escape(value, quote=True)


def render_table(river: River) -> str:
    head = ("<thead><tr>"
            "<th scope=\"col\">Wodowskaz</th>"
            "<th scope=\"col\">km od ujścia</th>"
            "<th scope=\"col\">Stan wody</th>"
            "<th scope=\"col\">Do stanu ostrzegawczego</th>"
            "<th scope=\"col\">Temperatura wody</th>"
            "<th scope=\"col\">Pomiar</th>"
            "</tr></thead>")
    body = []
    for row in river.rows:
        if row["level"] is None:
            level = "brak świeżego odczytu"
            margin = "—"
        else:
            level = fmt(row["level"], " cm")
            if row["warn"] is None:
                margin = "brak progu"
            else:
                delta = row["warn"] - row["level"]
                margin = (f"{fmt(round(delta))} cm poniżej" if delta > 0
                          else ("na progu" if delta == 0 else f"{fmt(abs(round(delta)))} cm powyżej"))
        stamp = parse_stamp(row["level_stamp"])
        when = stamp.strftime("%d.%m, %H:%M") if stamp else "—"
        body.append(
            f'<tr><th scope="row">{esc(row["station"])}'
            + (f' <span class="muted">({esc(row["voivodeship"])})</span>' if row["voivodeship"] else "")
            + f'</th><td>{fmt(row["km"])}</td><td>{level}</td><td>{margin}</td>'
            + f'<td>{fmt(row["temp"], " °C") if row["temp"] is not None else "—"}</td><td>{when}</td></tr>'
        )
    return ('<div class="tool-table-wrap"><table class="tool-table">'
            f'<caption>Wodowskazy IMGW na {esc(river.locative)} — ostatnie odczyty</caption>'
            + head + "<tbody>" + "".join(body) + "</tbody></table></div>")


PAGE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <meta name="description" content="{description}" />
  <link rel="preload" as="font" type="font/woff2" href="/assets/fonts/inter-400-latin.woff2" crossorigin>
  <link rel="preload" as="font" type="font/woff2" href="/assets/fonts/inter-400-latin-ext.woff2" crossorigin>
  <link rel="stylesheet" href="../css/style.css" />
<!--og-image:{image}-->
</head>
<body>
<header class="site-header"></header>
<main>
<section class="subpage-hero"><div class="container"><p class="eyebrow">Rzeki · dane IMGW-PIB</p><h1>{h1}</h1><p>{lead}</p></div></section>
<section class="section container article-layout"><article class="article-card">
{body}
</article></section>
</main>
<footer class="footer"><div class="container footer-grid"><p class="footer-author">Autor treści: <span rel="author">Maciej Baniewicz</span></p><p>© 2026 FishPoint.</p><p>Rzetelne opisy sprzętu wędkarskiego</p><p class="footer-legal"></p></div></footer>
<script defer src="../js/main.js"></script>
</body>
</html>
"""

REFRESH_SCRIPT = """<p class="live-refresh"><button type="button" class="btn-secondary" data-hydro-refresh data-river="{river}">Sprawdź odczyty na teraz</button> <span data-hydro-status role="status"></span></p>
<script>
(function () {
  "use strict";
  var button = document.currentScript.parentNode.querySelector("[data-hydro-refresh]");
  if (!button) return;
  var status = document.currentScript.parentNode.querySelector("[data-hydro-status]");
  var river = button.getAttribute("data-river");
  // Tabela w dokumencie pochodzi z przebudowy serwisu, więc może być o kilka
  // godzin starsza niż IMGW. Dociągamy pełny wykaz dopiero na żądanie —
  // odpytanie waży kilkaset kilobajtów, a aktualizuje kilka wierszy.
  button.addEventListener("click", function () {
    button.disabled = true;
    status.textContent = "Pobieram z IMGW…";
    fetch("https://danepubliczne.imgw.pl/api/data/hydro/")
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (all) {
        var rows = all.filter(function (d) { return d.rzeka === river; });
        var byName = {};
        rows.forEach(function (d) { byName[(d.stacja || "").toLowerCase()] = d; });
        var updated = 0;
        var table = document.querySelector("table.tool-table");
        (table ? table.querySelectorAll("tbody tr") : []).forEach(function (tr) {
          var name = (tr.querySelector("th") || {}).textContent || "";
          name = name.replace(/\\s*\\([^)]*\\)\\s*$/, "").trim().toLowerCase();
          var d = byName[name];
          if (!d || d.stan_wody === null || d.stan_wody === "") return;
          // Wiersz to <th> z nazwą stacji i pięć <td>: km, stan, zapas do progu,
          // temperatura, godzina pomiaru. querySelectorAll("td") nie zwraca <th>,
          // więc indeksy liczą się od kilometrażu, nie od nazwy.
          var cells = tr.querySelectorAll("td");
          if (cells.length < 5) return;
          cells[1].textContent = d.stan_wody + " cm";
          var warn = parseFloat(d.stan_ostrzegawczy);
          cells[2].textContent = "brak progu";
          if (!isNaN(warn)) {
            var delta = Math.round(warn - parseFloat(d.stan_wody));
            cells[2].textContent = delta > 0 ? delta + " cm poniżej"
              : (delta === 0 ? "na progu" : Math.abs(delta) + " cm powyżej");
          }
          var t = d.temperatura_wody;
          cells[3].textContent = (t === null || t === "") ? "—" : t + " °C";
          var m = /^(\\d{4})-(\\d{2})-(\\d{2})\\s+(\\d{2}):(\\d{2})/.exec(d.stan_wody_data_pomiaru || "");
          cells[4].textContent = m ? (m[3] + "." + m[2] + ", " + m[4] + ":" + m[5]) : "—";
          updated += 1;
        });
        var total = table ? table.querySelectorAll("tbody tr").length : 0;
        status.textContent = updated
          ? "Zaktualizowano " + updated + " z " + total + " wodowskazów."
          : "IMGW nie zwróciło teraz odczytów dla tej rzeki.";
      })
      .catch(function () {
        status.textContent = "Nie udało się połączyć z IMGW. Tabela pokazuje ostatni zapisany odczyt.";
      })
      .finally(function () { button.disabled = false; });
  });
})();
</script>"""


def render_river(river: River, built: datetime.date) -> str:
    stamp = river.newest_stamp
    count = len(river.rows)
    title = (f"Stan wody na {river.locative} — {count} "
             f"{plural(count, 'wodowskaz', 'wodowskazy', 'wodowskazów')} IMGW | FishPoint")
    description = (f"Stan wody i temperatura na {river.locative}: odczyty z {count} "
                   f"{plural(count, 'wodowskazu', 'wodowskazów', 'wodowskazów')} IMGW, progi ostrzegawcze, "
                   "spadek odcinka i co poziom zmienia dla wędkarza.")[:250]
    lead = (f"Wszystkie wodowskazy IMGW-PIB na {river.locative} w jednej tabeli — z progiem ostrzegawczym "
            "i temperaturą wody tam, gdzie jest mierzona."
            + (f" Najnowszy odczyt w tym zestawieniu pochodzi z {stamp}." if stamp else ""))

    faq_html = "".join(
        f'<section class="info-block"><h3>{esc(q)}</h3><p>{a}</p></section>'
        for q, a in faq_pairs(river)
    )
    course = "".join(f"<p>{sentence}</p>" for sentence in course_sentences(river))
    angling = "".join(f"<p>{sentence}</p>" for sentence in angling_sentences(river))

    body = f"""<h2 id="odczyty">Wodowskazy i ostatnie odczyty</h2>
<p>{reading_sentence(river)}</p>
{render_table(river)}
{REFRESH_SCRIPT.replace("{river}", esc(river.name))}
<p class="muted">Pomiar starszy niż {FRESH_DAYS} doby pokazujemy jako „—”. Jak czytać łatę: <a href="./#jak-czytac">strona działu</a>.</p>

<h2 id="bieg">Bieg {esc(river.genitive)} w liczbach</h2>
{course}

<h2 id="co-to-zmienia">Co te liczby zmieniają nad wodą</h2>
{angling}
<p>Więcej: <a href="../poradniki/pogoda-a-brania.html">pogoda a brania</a>, <a href="../pierwsze-kroki/lowiska/rzeki.html">łowiska rzeczne</a>, <a href="../poradniki/wedkarstwo-z-brzegu.html">wędkarstwo z brzegu</a>.</p>

<h2 id="faq">FAQ — stan wody na {esc(river.locative)}</h2>
{faq_html}

<div class="source-box"><h3>Skąd te dane i czego nie obejmują</h3><p>Odczyty, kilometraż, rzędne zer łat, progi i przepływy {esc(river.genitive)} pochodzą z <strong>publicznego API hydrologicznego IMGW-PIB</strong> (<a href="https://danepubliczne.imgw.pl/" rel="noopener" target="_blank">danepubliczne.imgw.pl</a>), zapis z {pl_date(built)}. Spadek {esc(river.genitive)} podajemy jako średnią dla {fmt(river.span_km)} km objętych pomiarami — nie jest to profil podłużny rzeki i nie opisuje wody powyżej stacji {esc(river.rows[-1]["station"])}. <a href="./#jak-czytac">Jak czytać wodowskaz</a>. Nie zastępuje sprawdzenia <a href="../narzedzia/okresy-ochronne.html">okresów ochronnych</a> ani zezwolenia.</p></div>"""

    return PAGE.format(
        title=esc(title),
        description=esc(description),
        image=LEAD_IMAGE,
        h1=esc(f"Stan wody na {river.locative}"),
        lead=lead,
        body=body,
    )


def render_hub(rivers: list[River], others: list[River], built: datetime.date) -> str:
    total_stations = sum(len(r.rows) for r in rivers) + sum(len(r.rows) for r in others)
    alarmed = [r for r in rivers if r.above_alarm]
    warned = [r for r in rivers if r.above_warning and not r.above_alarm]

    if alarmed:
        state = (f"Stan alarmowy jest w tej chwili przekroczony na {len(alarmed)} "
                 f"{plural(len(alarmed), 'rzece', 'rzekach', 'rzekach')}: "
                 + join_pl([r.name for r in alarmed]) + ".")
    elif warned:
        state = (f"Nigdzie nie ma przekroczonego stanu alarmowego; stan ostrzegawczy przekracza {len(warned)} "
                 f"{plural(len(warned), 'rzeka', 'rzeki', 'rzek')}: " + join_pl([r.name for r in warned]) + ".")
    else:
        state = "W ostatnich odczytach żadna z opisanych rzek nie przekracza stanu ostrzegawczego."

    coldest = min((r for r in rivers if r.temps),
                  key=lambda r: min(row["temp"] for row in r.temps), default=None)
    warmest = max((r for r in rivers if r.temps),
                  key=lambda r: max(row["temp"] for row in r.temps), default=None)
    temp_line = ""
    if coldest and warmest and coldest is not warmest:
        temp_line = (f" Najzimniejszą wodę raportuje w tej chwili {coldest.name} "
                     f"({fmt(min(row['temp'] for row in coldest.temps), ' °C')}), najcieplejszą — {warmest.name} "
                     f"({fmt(max(row['temp'] for row in warmest.temps), ' °C')}).")

    rows = []
    for river in rivers:
        temps = river.temps
        summary = (f"{len(river.measured)} z {len(river.rows)}" if river.measured else "brak")
        label, _ = river.character
        if len(temps) > 1:
            temp_cell = fmt(min(r["temp"] for r in temps), "") + "–" + fmt(max(r["temp"] for r in temps), " °C")
        elif temps:
            temp_cell = fmt(temps[0]["temp"], " °C")
        else:
            temp_cell = "—"
        rows.append(
            f'<tr><th scope="row"><a href="{river.slug}.html">{esc(river.name)}</a></th>'
            f'<td>{len(river.rows)}</td><td>{esc(label)}</td>'
            f'<td>{fmt(river.gradient, " m/km")}</td>'
            f'<td>{esc(", ".join(river.voivodeships))}</td>'
            f'<td>{summary}</td><td>{temp_cell}</td></tr>'
        )

    other_names = ", ".join(sorted((r.name for r in others), key=pl_key))

    body = f"""<h2 id="stan-teraz">Gdzie woda jest dziś wysoka</h2>
<p>{state}{temp_line} Progi ostrzegawcze i alarmowe wyznacza IMGW dla ochrony przeciwpowodziowej — dla wędkarza są sygnałem o dojściu do brzegu i o rumowisku niesionym przez rzekę, a nie zakazem wjazdu nad wodę.</p>

<h2 id="jak-czytac">Jak czytać wodowskaz</h2>
<p>Stan wody to wysokość lustra ponad <strong>zerem łaty</strong> danej stacji, a nie głębokość rzeki. Zero każdej łaty leży na innej rzędnej, ustalonej przy zakładaniu wodowskazu — czasem, jak przy ujściu Wisły, poniżej poziomu morza. Dlatego zestawianie dwóch stacji ze sobą nic nie mówi o tym, gdzie jest głębiej; sens ma wyłącznie porównanie jednej stacji w czasie.</p>
<p>Stan ostrzegawczy i alarmowy to progi przeciwpowodziowe, nie wędkarskie. Ich przekroczenie nie zamyka łowiska z automatu, ale oznacza podmyte brzegi, zalane dojścia i zmienione dno. Przepływ, podawany w metrach sześciennych na sekundę, mówi z kolei o objętości niesionej wody i lepiej niż sam poziom oddaje, jak mocny jest nurt.</p>

<h2 id="rzeki">Rzeki z własną stroną</h2>
<p>Stronę dostaje rzeka z co najmniej {MIN_STATIONS} wodowskazami: przy mniejszej liczbie punktów nie da się policzyć spadku odcinka ani opisać biegu, a strona powielałaby jeden wiersz tabeli. Pomijamy też nazwy, pod którymi w wykazie IMGW kryje się kilka odrębnych rzek — Biała, Bystrzyca, Czarna, Kamienna i Piława występują w Polsce wielokrotnie, a ich kilometraż liczony jest od różnych ujść.</p>
<div class="tool-table-wrap"><table class="tool-table"><caption>Rzeki opisane w dziale — wodowskazy, spadek odcinka i zasięg</caption><thead><tr><th scope="col">Rzeka</th><th scope="col">Wodowskazy</th><th scope="col">Charakter</th><th scope="col">Spadek</th><th scope="col">Województwa</th><th scope="col">Świeże odczyty</th><th scope="col">Temperatura</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>

<h2 id="pozostale">Pozostałe rzeki w wykazie IMGW</h2>
<p>Te cieki mają w wykazie od jednego do trzech wodowskazów albo dzielą nazwę z inną rzeką. Własnej strony nie mają, ale ich odczyty są w narzędziu <a href="../narzedzia/stany-wod.html">Stany wód na żywo</a>, z filtrem po województwie i nazwie: {esc(other_names)}.</p>

<h2 id="po-co">Po co wędkarzowi wodowskaz</h2>
<p>Stan wody odpowiada na pytanie, którego nie rozstrzygnie żaden kalendarz: czy da się dziś wejść na to stanowisko. Wysoka woda zalewa łachy i dojścia, przesuwa linię brzegu i niesie zawiesinę; niska odsłania strukturę dna, którą warto zapamiętać na resztę sezonu.</p>
<p>Drugim parametrem jest temperatura wody. Porządkuje aktywność gatunków lepiej niż data w kalendarzu — i to ona tłumaczy, dlaczego ten sam wyjazd wypada inaczej w dwóch kolejnych latach. Zestawienie z pogodą opisuje <a href="../poradniki/pogoda-a-brania.html">osobny poradnik</a>, a listę {len(rivers)} rzek z tego działu znajdziesz w tabeli wyżej.</p>

<h2 id="faq">FAQ — stany wód i wędkowanie</h2>
<section class="info-block"><h3>Skąd pochodzą te dane?</h3><p>Z publicznego API hydrologicznego IMGW-PIB. Zapisujemy je przy każdej przebudowie serwisu, a przycisk na stronie rzeki pobiera bieżące wartości bezpośrednio z IMGW, już w Twojej przeglądarce.</p></section>
<section class="info-block"><h3>Czy stan wody mówi, kiedy będą brania?</h3><p>Nie. Mówi o warunkach: o dostępie do brzegu, o przejrzystości i o sile nurtu. Nie podajemy go jako prognozy wyniku, bo dane hydrologiczne takiej prognozy nie niosą.</p></section>
<section class="info-block"><h3>Dlaczego niektóre rzeki nie mają temperatury wody?</h3><p>Temperaturę mierzy tylko część stacji hydrologicznych. Brak wartości oznacza, że na tym odcinku nikt jej nie raportuje — nie że akurat dziś zabrakło pomiaru.</p></section>
<section class="info-block"><h3>Czy wysoka woda oznacza zakaz wędkowania?</h3><p>Sam poziom niczego nie zakazuje, ale przy wezbraniu obowiązywać mogą lokalne zakazy wstępu na wały i tereny zalewowe, wydawane przez gminę lub zarządcę wód. Sprawdzaj je osobno.</p></section>

<div class="source-box"><h3>Źródła i granice działu</h3><p><strong>Dane: IMGW-PIB, publiczne API hydrologiczne</strong> (<a href="https://danepubliczne.imgw.pl/" rel="noopener" target="_blank">danepubliczne.imgw.pl</a>), zapis z {pl_date(built)}, {total_stations} wodowskazów w wykazie. Podział na charakter górski, podgórski i nizinny liczymy wyłącznie ze spadku zer łat między skrajnymi wodowskazami danej rzeki — to przybliżenie odcinka objętego pomiarami, nie klasyfikacja hydrologiczna całego cieku. Dział nie zastępuje sprawdzenia <a href="../narzedzia/okresy-ochronne.html">okresów ochronnych</a>, wymiarów ani zezwolenia na obwód rybacki.</p></div>"""

    return PAGE.format(
        title=esc(f"Stany wód na polskich rzekach — {len(rivers)} rzek, dane IMGW | FishPoint"),
        description=esc("Aktualne stany wody i temperatura na polskich rzekach z wodowskazów IMGW-PIB. "
                        "Progi ostrzegawcze, spadek odcinka i co poziom wody zmienia dla wędkarza."),
        image=LEAD_IMAGE,
        h1=esc("Stany wód na polskich rzekach"),
        lead=("Odczyty z wodowskazów IMGW-PIB zebrane rzeka po rzece: poziom, temperatura wody i odległość "
              "do stanu ostrzegawczego. Bez obietnic o braniach — same warunki, w jakich zastaniesz wodę."),
        body=body,
    )


# --- odmiana nazw ----------------------------------------------------------

# Miejscownik nazw rzek. Reguła „-a → -ie" ma w polszczyźnie tyle wyjątków
# (Odra → Odrze, Warta → Warcie), że tabela jest uczciwsza od algorytmu:
# błędna odmiana w nagłówku H1 widać od razu i psuje wiarygodność strony.
LOCATIVE = {
    "Wisła": "Wiśle", "Odra": "Odrze", "Warta": "Warcie", "Bóbr": "Bobrze",
    "Narew": "Narwi", "Noteć": "Noteci", "San": "Sanie", "Kamienna": "Kamiennej",
    "Bystrzyca": "Bystrzycy", "Nysa Kłodzka": "Nysie Kłodzkiej", "Bug": "Bugu",
    "Wisłok": "Wisłoku", "Wieprz": "Wieprzu", "Czarna": "Czarnej",
    "Dunajec": "Dunajcu", "Nysa Łużycka": "Nysie Łużyckiej", "Biała": "Białej",
    "Raba": "Rabie", "Wieprza": "Wieprzy", "Wisłoka": "Wisłoce",
    "Parsęta": "Parsęcie", "Pilica": "Pilicy", "Drwęca": "Drwęcy",
    "Kwisa": "Kwisie", "Rega": "Redze", "Kłodnica": "Kłodnicy", "Soła": "Sole",
    "Biebrza": "Biebrzy", "Pasłęka": "Pasłęce", "Skawa": "Skawie",
    "Barycz": "Baryczy", "Prosna": "Prośnie", "Słupia": "Słupi",
    "Łupawa": "Łupawie", "Ruda": "Rudzie", "Brda": "Brdzie",
    "Wierzyca": "Wierzycy", "Radunia": "Raduni", "Ropa": "Ropie",
    "Supraśl": "Supraśli", "Wda": "Wdzie", "Piława": "Piławie",
    "Mała Panew": "Małej Panwi", "Kaczawa": "Kaczawie", "Drawa": "Drawie",
}


# Dopełniacz nazw rzek — potrzebny w nagłówku „Bieg …" i w zdaniach o spadku.
# Tabela zamiast reguły z tego samego powodu co przy miejscowniku.
GENITIVE = {
    "Wisła": "Wisły", "Odra": "Odry", "Warta": "Warty", "Bóbr": "Bobru",
    "Narew": "Narwi", "Noteć": "Noteci", "San": "Sanu", "Kamienna": "Kamiennej",
    "Bystrzyca": "Bystrzycy", "Nysa Kłodzka": "Nysy Kłodzkiej", "Bug": "Bugu",
    "Wisłok": "Wisłoka", "Wieprz": "Wieprza", "Czarna": "Czarnej",
    "Dunajec": "Dunajca", "Nysa Łużycka": "Nysy Łużyckiej", "Biała": "Białej",
    "Raba": "Raby", "Wieprza": "Wieprzy", "Wisłoka": "Wisłoki",
    "Parsęta": "Parsęty", "Pilica": "Pilicy", "Drwęca": "Drwęcy",
    "Kwisa": "Kwisy", "Rega": "Regi", "Kłodnica": "Kłodnicy", "Soła": "Soły",
    "Biebrza": "Biebrzy", "Pasłęka": "Pasłęki", "Skawa": "Skawy",
    "Barycz": "Baryczy", "Prosna": "Prosny", "Słupia": "Słupi",
    "Łupawa": "Łupawy", "Ruda": "Rudy", "Brda": "Brdy",
    "Wierzyca": "Wierzycy", "Radunia": "Raduni", "Ropa": "Ropy",
    "Supraśl": "Supraśli", "Wda": "Wdy", "Piława": "Piławy",
    "Mała Panew": "Małej Panwi", "Kaczawa": "Kaczawy", "Drawa": "Drawy",
}


def locative_for(name: str) -> str | None:
    """Miejscownik i dopełniacz muszą być oba znane — bez tego nie budujemy strony."""
    if name in LOCATIVE and name in GENITIVE:
        return LOCATIVE[name]
    return None


# --- główny przebieg -------------------------------------------------------

def main() -> int:
    now = datetime.datetime.now()
    built = now.date()
    stations, live = fetch_stations()

    grouped: dict[str, list[dict]] = {}
    for row in stations:
        name = (row.get("rzeka") or "").strip()
        if not name or name in NOT_RIVERS:
            continue
        grouped.setdefault(name, []).append(row)

    selected, others, missing_locative, ambiguous = [], [], [], []
    for name, rows in grouped.items():
        river = River(name, rows, now)
        if len(river.rows) >= MIN_STATIONS and not river.is_single_watercourse:
            ambiguous.append(name)
            others.append(river)
            continue
        if len(river.rows) >= MIN_STATIONS:
            locative = locative_for(name)
            if locative is None:
                # Bez pewnej odmiany nie budujemy strony — H1 z błędem gramatycznym
                # kosztuje więcej niż brak strony dla jednej rzeki.
                missing_locative.append(name)
                others.append(river)
                continue
            river.locative = locative
            river.genitive = GENITIVE[name]
            selected.append(river)
        else:
            others.append(river)

    selected.sort(key=lambda r: (-len(r.rows), r.name.lower()))

    OUT_DIR.mkdir(exist_ok=True)
    keep = {"index.html"}
    for river in selected:
        target = OUT_DIR / f"{river.slug}.html"
        keep.add(target.name)
        target.write_text(render_river(river, built), encoding="utf-8")

    (OUT_DIR / "index.html").write_text(render_hub(selected, others, built), encoding="utf-8")

    # Rzeka mogła wypaść z progu (zamknięty wodowskaz) — nie zostawiamy po niej
    # osieroconej strony, bo hub przestałby ją wymieniać, a sitemapa dalej by ją niosła.
    for path in OUT_DIR.glob("*.html"):
        if path.name not in keep:
            path.unlink()
            log(f"usunięto nieaktualną stronę: {path.name}")

    if ambiguous:
        log("pominięte (kilka różnych rzek o tej samej nazwie): " + ", ".join(sorted(ambiguous)))
    if missing_locative:
        log("pominięte (brak odmiany w tabeli LOCATIVE): " + ", ".join(sorted(missing_locative)))
    log(f"zapisano {len(selected)} stron rzek + hub; źródło: {'IMGW na żywo' if live else 'zrzut lokalny'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
