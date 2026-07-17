#!/usr/bin/env python3
"""Focused regression contracts for the July 2026 FishPoint audit fixes."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.headings: list[list[int | str]] = []
        self.main_text: list[str] = []
        self.json_ld: list[str] = []
        self._json_ld: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        self.stack.append(tag)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append([int(tag[1]), ""])
        if tag == "script" and attr.get("type") == "application/ld+json":
            self._json_ld = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json_ld is not None:
            self.json_ld.append(self._json_ld)
            self._json_ld = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index] == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data: str) -> None:
        if self._json_ld is not None:
            self._json_ld += data
        if "main" in self.stack or "title" in self.stack:
            self.main_text.append(data)
        if self.headings and self.stack and self.stack[-1] in {
            "h1", "h2", "h3", "h4", "h5", "h6"
        }:
            self.headings[-1][1] = str(self.headings[-1][1]) + data


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="replace")


def parse(relative: str) -> PageParser:
    parser = PageParser()
    parser.feed(read(relative))
    return parser


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip().lower()


def local_path(url: str) -> str:
    path = urlparse(url).path.lstrip("/")
    if not path:
        return "index.html"
    return f"{path}index.html" if path.endswith("/") else path


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    sitemap = ET.fromstring(read("sitemap.xml"))
    urls = [node.text or "" for node in sitemap.findall("s:url/s:loc", SITEMAP_NS)]
    check(len(urls) == 174 and len(set(urls)) == 174, "sitemap must contain 174 unique URLs", failures)

    parsed: dict[str, PageParser] = {}
    for url in urls:
        relative = local_path(url)
        check((ROOT / relative).is_file(), f"missing sitemap target: {relative}", failures)
        if not (ROOT / relative).is_file():
            continue
        page = parse(relative)
        parsed[url] = page
        levels = [int(level) for level, _ in page.headings]
        check(levels.count(1) == 1, f"{relative}: expected exactly one H1", failures)
        check(
            all(next_level <= level + 1 for level, next_level in zip(levels, levels[1:])),
            f"{relative}: heading hierarchy skips a level",
            failures,
        )
        for raw_json in page.json_ld:
            try:
                json.loads(raw_json)
            except json.JSONDecodeError as error:
                failures.append(f"{relative}: invalid JSON-LD: {error}")

    # The three legal FAQ corrections must be identical in schema and visible copy.
    for relative in ("lowiska/slaskie.html", "lowiska/pomorskie.html", "lowiska/zachodniopomorskie.html"):
        page = parse(relative)
        visible = normalize(" ".join(page.main_text))
        for raw_json in page.json_ld:
            document = json.loads(raw_json)
            for node in walk(document):
                if not isinstance(node, dict) or node.get("@type") != "FAQPage":
                    continue
                for question in node.get("mainEntity", []):
                    answer = normalize(str((question.get("acceptedAnswer") or {}).get("text", "")))
                    check(not answer or answer in visible, f"{relative}: FAQ schema differs from visible answer", failures)

    calendar = read("poradniki/kalendarz-bran.html").lower()
    check("sandacz od 1 marca do 31 maja" in calendar, "sandacz period is not 1 March–31 May", failures)
    check("sandacz od 1 stycznia" not in calendar, "obsolete sandacz start date remains", failures)

    marine = read("aktualnosci/wedkarstwo-morskie-dla-poczatkujacych.html").lower()
    check("rejs za dorszem" not in marine, "protected cod is still recommended as a trip target", failures)
    check("1 stycznia do 31 grudnia" in marine or "cały rok" in marine, "year-round cod protection is missing", failures)

    algae = parse("aktualnosci/zlota-alga-lato-2026.html")
    algae_h1 = " ".join(str(text) for level, text in algae.headings if int(level) == 1).lower()
    check("wraca" not in algae_h1, "golden-algae H1 asserts an unconfirmed return", failures)

    for fish_page in (ROOT / "ryby").glob("*.html"):
        html = fish_page.read_text(encoding="utf-8", errors="replace")
        check("iucnredlist.org/search" not in html, f"{fish_page.relative_to(ROOT)} emits an IUCN search URL", failures)
        for href in re.findall(r'href=["\']([^"\']*iucnredlist\.org[^"\']*)', html, re.I):
            check("/species/" in href, f"{fish_page.relative_to(ROOT)} has a non-species IUCN URL", failures)

    for family in ("tematy", "kuchnia", "aktualnosci"):
        metadata = json.loads(read(f"assets/img/{family}/_meta.json"))
        for key, record in metadata.items():
            filename = record.get("file")
            check(bool(filename), f"{family}/{key}: attribution record lacks file", failures)
            if filename:
                check((ROOT / "assets" / "img" / family / filename).is_file(), f"{family}/{key}: missing {filename}", failures)

    check("2GekupS_N9s/hqdefault.jpg" not in read("humor/filmiki.html"), "known 404 video thumbnail remains", failures)
    check("(klasyczna." not in read("kuchnia/smazony-okon-sandacz.html"), "truncated recipe description remains", failures)

    modified_pages = (
        "aktualnosci/jak-lowic-lina.html",
        "aktualnosci/przyneta-na-spinning.html",
        "lowiska/index.html",
        "lowiska/pomorskie.html",
        "narzedzia/czy-moge-zabrac-rybe.html",
        "narzedzia/kalendarz-ksiezycowy.html",
        "pierwsze-kroki/index.html",
        "pierwsze-kroki/pierwszy-zestaw-wedkarski-budzet.html",
        "pierwsze-kroki/twoj-pierwszy-wyjazd-na-ryby.html",
        "poradniki/index.html",
        "ryby/leszcz.html",
        "ryby/ploc.html",
        "ryby/szczupak.html",
        "ryby/wegorz.html",
    )
    for relative in modified_pages:
        html = read(relative)
        check(
            re.search(r"content-meta:[^\n]*modified=2026-07-17", html) is not None,
            f"{relative}: stale content-meta modified date",
            failures,
        )
        if relative not in {"lowiska/index.html", "pierwsze-kroki/index.html", "poradniki/index.html"}:
            check('article:modified_time" content="2026-07-17' in html, f"{relative}: stale generated modified time", failures)

    if failures:
        print("Audit contracts failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Audit contracts: ok ({len(urls)} sitemap pages; 3 FAQ parity checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
