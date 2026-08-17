#!/usr/bin/env python3
"""Focused regression contracts for the July 2026 FishPoint audit fixes."""

from __future__ import annotations

import hashlib
import ast
import struct

import datetime
import json
import os
import re
import sys
from collections import Counter
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
INTERNAL_HOSTS = {"fish-point.pl", "www.fish-point.pl"}

# Kontrakty dat, roku obowiązywania i wariantów obrazów sprawdzają dokładnie
# te reguły, które stosuje generator — dlatego korzystają z jego definicji.
sys.path.insert(0, str(ROOT))
import seo_inject  # noqa: E402



class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.headings: list[list[int | str]] = []
        self.class_stack: list[set[str]] = []
        self.content_advantage_count = 0
        self.content_advantage_in_article = 0
        self.content_advantage_in_hero = 0
        self.tldr_in_article = 0
        self.main_text: list[str] = []
        self.json_ld: list[str] = []
        self.metadata: dict[str, str] = {}
        self.metadata_counts: dict[str, int] = {}
        self.article_visual_count = 0
        self.article_images: list[dict[str, str | None]] = []
        self.article_license_links = 0
        self.hrefs: list[str] = []
        self.contextual_hrefs: list[str] = []
        self.toc_hrefs: list[str] = []
        self.ids: list[str] = []
        self.tables: list[dict[str, int]] = []
        self.title_text: list[str] = []
        self._in_document_title = False
        self._json_ld: str | None = None
        self._main_depth = 0
        self._toc_depth = 0
        self._active_table: dict[str, int] | None = None
        self._submenu_links: list[list[str]] = []
        self.submenu_links: list[list[str]] = []
        self.news_cards: list[tuple[str | None, list[str]]] = []
        self._news_category: str | None = None
        self._blog_card_links: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())
        inside_article = any("article-card" in item for item in self.class_stack)
        inside_hero = any("subpage-hero" in item for item in self.class_stack)
        inside_article_visual = any("article-lead-visual" in item for item in self.class_stack)
        self.class_stack.append(classes)
        if "content-advantage" in classes:
            self.content_advantage_count += 1
            self.content_advantage_in_article += int(inside_article)
            self.content_advantage_in_hero += int(inside_hero)
        if "tldr" in classes:
            self.tldr_in_article += int(inside_article)
        if "article-lead-visual" in classes:
            self.article_visual_count += 1
        if tag == "img" and "article-image" in classes:
            self.article_images.append(attr)
        self.stack.append(tag)
        if attr.get("id"):
            self.ids.append(attr["id"])
        if tag == "main":
            self._main_depth += 1
        if tag == "nav" and "toc" in (attr.get("class") or "").split():
            self._toc_depth += 1
        if tag == "ul" and "sub" in (attr.get("class") or "").split():
            self._submenu_links.append([])
        if tag == "div" and "section-heading" in (attr.get("class") or "").split():
            self._news_category = attr.get("id")
        if tag == "article" and "blog-card" in (attr.get("class") or "").split():
            self._blog_card_links = []
        if tag == "table":
            self._active_table = {"captions": 0, "th": 0, "scoped_th": 0}
            self.tables.append(self._active_table)
        elif tag == "caption" and self._active_table is not None:
            self._active_table["captions"] += 1
        elif tag == "th" and self._active_table is not None:
            self._active_table["th"] += 1
            self._active_table["scoped_th"] += int(bool(attr.get("scope")))
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append([int(tag[1]), ""])
        if tag == "script" and attr.get("type") == "application/ld+json":
            self._json_ld = ""
        if tag == "title" and "head" in self.stack:
            self._in_document_title = True
        if tag == "meta":
            key = attr.get("name") or attr.get("property")
            content = attr.get("content")
            if key and content is not None:
                self.metadata[key] = content
                self.metadata_counts[key] = self.metadata_counts.get(key, 0) + 1
        if tag == "a" and attr.get("href") is not None:
            href = attr["href"]
            self.hrefs.append(href)
            if self._main_depth:
                self.contextual_hrefs.append(href)
            if self._toc_depth:
                self.toc_hrefs.append(href)
            if self._submenu_links:
                self._submenu_links[-1].append(href)
            if self._blog_card_links is not None:
                self._blog_card_links.append(href)
            if inside_article_visual and "license" in (attr.get("rel") or "").split():
                self.article_license_links += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "article" and self._blog_card_links is not None:
            self.news_cards.append((self._news_category, self._blog_card_links))
            self._blog_card_links = None
        if tag == "title":
            self._in_document_title = False
        if tag == "script" and self._json_ld is not None:
            self.json_ld.append(self._json_ld)
            self._json_ld = None
        if tag == "ul" and self._submenu_links:
            self.submenu_links.append(self._submenu_links.pop())
        if tag == "nav" and self._toc_depth:
            self._toc_depth -= 1
        if tag == "main" and self._main_depth:
            self._main_depth -= 1
        if tag == "table":
            self._active_table = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index] == tag:
                self.stack = self.stack[:index]
                self.class_stack = self.class_stack[:index]
                break

    def handle_data(self, data: str) -> None:
        if self._json_ld is not None:
            self._json_ld += data
        if "main" in self.stack or "title" in self.stack:
            self.main_text.append(data)
        if self._in_document_title:
            self.title_text.append(data)
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
    normalized = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip().lower()
    return re.sub(r"\s+([,.;:!?])", r"\1", normalized)

def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def local_link_target(source: Path, href: str) -> Path | None:
    parsed = urlparse(href)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc and parsed.netloc.lower() not in INTERNAL_HOSTS:
        return None
    path = unquote(parsed.path)
    if not path:
        return ROOT / "index.html" if parsed.netloc else source
    target = ROOT / path.lstrip("/") if path.startswith("/") or parsed.netloc else source.parent / path
    target = target.resolve()
    return target / "index.html" if target == ROOT or path.endswith("/") else target


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


def tool_image_map() -> dict[str, str]:
    """Odczytuje literalną mapę obrazów narzędzi z generatora przez AST."""
    tree = ast.parse(read("seo_inject.py"), filename="seo_inject.py")
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "TOOL_IMG" for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, dict) and all(
                isinstance(key, str) and isinstance(path, str) for key, path in value.items()
            ):
                return value
    raise ValueError("seo_inject.py: TOOL_IMG must be a literal string map")


def image_width(path: Path) -> int:
    """Zwraca szerokość PNG/JPEG bez zależności od bibliotek obrazu."""
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">I", data[16:20])[0]
    if data.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            while offset < len(data) and data[offset] == 0xFF:
                offset += 1
            marker = data[offset]
            offset += 1
            if marker in {0xD8, 0xD9}:
                continue
            length = struct.unpack(">H", data[offset:offset + 2])[0]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                return struct.unpack(">H", data[offset + 5:offset + 7])[0]
            offset += length
    raise ValueError(f"{path}: unsupported or invalid image")


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    sitemap = ET.fromstring(read("sitemap.xml"))
    urls = [node.text or "" for node in sitemap.findall("s:url/s:loc", SITEMAP_NS)]
    check(len(urls) == 205 and len(set(urls)) == 205, "sitemap must contain 205 unique URLs", failures)

    visual_pages = 0
    regional_visuals = 0
    expected_inline_visuals = {
        "pierwsze-kroki/jak-nabic-przynete-i-odhaczyc-rybe.html":
            ("/assets/img/tematy/schemat-catch-release.svg",),
        "techniki/spinning.html": (
            "/assets/img/tematy/schemat-spinning.svg",
            "/assets/img/ryby/szczupak-wobler.jpg",
            "/assets/img/ryby/szczupak-streamer.jpg",
        ),
        "techniki/podlodowe.html": ("/assets/img/tematy/mormyszki-podlodowe.jpg",),
        "techniki/feeder.html": ("/assets/img/tematy/leszcze-podbierak.jpg",),
        "ryby/okon.html": ("/assets/img/ryby/okon-trawa.jpg",),
        "ryby/jesiotr.html": ("/assets/img/ryby/jesiotr-brzeg.jpg",),
        "ryby/lin.html": (
            "/assets/img/ryby/lin-dlon.jpg",
            "/assets/img/ryby/liny-trzy.jpg",
            "/assets/img/ryby/lin-dzien.jpg",
        ),
        "sprzet/przynety.html": (
            "/assets/img/tematy/gumy-kopyta.jpg",
            "/assets/img/tematy/guma-glowka-dlon.jpg",
            "/assets/img/tematy/blystki-wahadlowe.jpg",
        ),
        "pierwsze-kroki/sprzet/przynety.html": ("/assets/img/tematy/pudelko-przynet.jpg",),
        "sprzet/jak-wybrac-kolowrotek.html": ("/assets/img/tematy/kolowrotek-ninja.jpg",),
        "sprzet/plecionki-zylki.html": ("/assets/img/tematy/wedka-plecionka.jpg",),
        "poradniki/zanety-domowe.html": ("/assets/img/tematy/zaneta-kukurydza.jpg",),
        "pierwsze-kroki/lowiska/jeziora.html": ("/assets/img/tematy/jezioro-swit.jpg",),
        "poradniki/pogoda-a-brania.html": ("/assets/img/tematy/jezioro-deszcz.jpg",),
        "poradniki/lowienie-zima.html": ("/assets/img/tematy/rozlewisko-zima.jpg",),
        "poradniki/wedkarstwo-z-brzegu.html": ("/assets/img/tematy/jezioro-poranek.jpg",),
        "poradniki/lowienie-nocne.html": ("/assets/img/ryby/liny-noc.jpg",),
        "techniki/karpiowanie.html": (
            "/assets/img/tematy/schemat-karpiowy.svg",
            "/assets/img/ryby/karp-jezioro.jpg",
        ),
        "ryby/szczupak.html": (
            "/assets/img/ryby/szczupak-guma.jpg",
            "/assets/img/ryby/szczupak-ponton.jpg",
            "/assets/img/ryby/szczupak-las.jpg",
        ),
        "ryby/karp.html": (
            "/assets/img/ryby/karp-lustrzen-jesien.jpg",
            "/assets/img/ryby/karp-mata-podbierak.jpg",
            "/assets/img/ryby/karp-podbierak-miarka.jpg",
        ),
        "ryby/karas.html": (
            "/assets/img/ryby/karas-kukurydza.jpg",
            "/assets/img/ryby/karas-duzy.jpg",
        ),
        "poradniki/wedkarstwo-z-lodzi.html": ("/assets/img/ryby/szczupak-ponton-lato.jpg",),
        "sprzet/kolowrotki.html": ("/assets/img/tematy/kolowrotek-golden-rn2000-szpula.jpg",),
        "sprzet/wedki.html": (
            "/assets/img/tematy/wedka-kolowrotek-abu-garcia.jpg",
            "/assets/img/tematy/wedka-spinningowa-abu-garcia.jpg",
        ),
        "sprzet/akcesoria.html": ("/assets/img/tematy/podbierak.jpg",),
        "techniki/splawik.html": ("/assets/img/tematy/schemat-splawik.svg",),
        "techniki/feeder-dla-poczatkujacych.html": ("/assets/img/tematy/schemat-feeder.svg",),
        "poradniki/catch-and-release.html": ("/assets/img/tematy/schemat-catch-release.svg",),
        "poradniki/echosondy.html": ("/assets/img/tematy/schemat-echosonda.svg",),
        "poradniki/wezly-wedkarskie.html": ("/assets/img/tematy/schemat-wezel.svg",),
        "kuchnia/przygotowanie-ryby.html": ("/assets/img/tematy/schemat-pakowanie.svg",),
        "aktualnosci/zezwolenia-online-2026.html": ("/assets/img/tematy/schemat-e-zezwolenie.svg",),
        "aktualnosci/zakaz-polowu-bobr-lipiec-2026.html":
            ("/assets/img/tematy/schemat-monitoring-wody.svg",),
        "narzedzia/czy-moge-zabrac-rybe.html": ("/assets/img/tematy/schemat-pomiar-ryby.svg",),
    }
    observed_inline_visuals: dict[str, list[str]] = {}
    faq_parity_pages = 0
    parsed: dict[str, PageParser] = {}
    expected_about = {
        "techniki/spinning.html": {("DefinedTerm", "Spinning")},
        "techniki/feeder.html": {("DefinedTerm", "Feeder")},
        "techniki/splawik.html": {("DefinedTerm", "Wędkarstwo spławikowe")},
        "techniki/karpiowanie.html": {("DefinedTerm", "Wędkarstwo karpiowe")},
        "techniki/muchowe.html": {("DefinedTerm", "Wędkarstwo muchowe")},
        "techniki/podlodowe.html": {("DefinedTerm", "Wędkarstwo podlodowe")},
        "techniki/trolling.html": {("DefinedTerm", "Trolling")},
        "aktualnosci/zakaz-polowu-bobr-lipiec-2026.html": {
            ("RiverBodyOfWater", "Bóbr"),
        },
        "aktualnosci/mistrzostwa-polski-splawik-swierkocin-2026.html": {
            ("DefinedTerm", "Wędkarstwo spławikowe"),
            ("RiverBodyOfWater", "Warta"),
            ("Place", "Świerkocin"),
        },
        "aktualnosci/troc-jeziorowa-85-kg-tarnobrzeg-2026.html": {
            ("LakeBodyOfWater", "Jezioro Tarnobrzeskie"),
        },
    }
    for url in urls:
        relative = local_path(url)
        check((ROOT / relative).is_file(), f"missing sitemap target: {relative}", failures)
        if not (ROOT / relative).is_file():
            continue
        page = parse(relative)
        parsed[url] = page
        source = read(relative)
        for key in (
            "author", "robots", "og:title", "og:description", "og:url", "og:image",
            "twitter:title", "twitter:description", "twitter:image",
        ):
            check(
                page.metadata_counts.get(key) == 1,
                f"{relative}: expected exactly one {key} meta tag",
                failures,
            )
        if "<!--article-visual:auto-->" in source:
            visual_pages += 1
            check(
                source.count("<!--article-visual:auto-->") == 1
                and source.count("<!--/article-visual:auto-->") == 1,
                f"{relative}: article visual markers are not idempotent",
                failures,
            )
            check(page.article_visual_count == 1,
                  f"{relative}: expected exactly one article lead visual", failures)
            check(len(page.article_images) == 1,
                  f"{relative}: expected exactly one article lead image", failures)
            lead_block = re.search(
                r"<!--article-visual:auto-->(.*?)<!--/article-visual:auto-->",
                source,
                re.S,
            )
            lead_owned = any(
                f"({name})" in (lead_block.group(1) if lead_block else "")
                for name in seo_inject.UNSOURCED_LICENSES
            )
            check(page.article_license_links == (0 if lead_owned else 1),
                  f"{relative}: article lead image lacks one license source", failures)
            if page.article_images:
                image = page.article_images[0]
                src = image.get("src") or ""
                width = image.get("width") or ""
                height = image.get("height") or ""
                check(src.startswith("/") and (ROOT / src.lstrip("/")).is_file(),
                      f"{relative}: article lead image is missing: {src}", failures)
                check(width.isdigit() and height.isdigit() and int(width) >= 800 and int(height) > 0,
                      f"{relative}: article lead image has invalid intrinsic dimensions", failures)
                check(page.metadata.get("og:image") == f"https://fish-point.pl{src}",
                      f"{relative}: article lead image and og:image differ", failures)
            check(
                not re.search(r'class=["\'][^"\']*\barticle-figure\b', source, re.I),
                f"{relative}: automatic lead duplicates an authored article figure",
                failures,
            )
            if relative.startswith("lowiska/") and relative != "lowiska/index.html":
                regional_visuals += 1
                check(
                    "nie przedstawia konkretnego łowiska w tym regionie" in source,
                    f"{relative}: regional illustration lacks a non-location disclaimer",
                    failures,
                )
        inline_blocks = re.findall(
            r"<!--inline-visual:auto-->(.*?)<!--/inline-visual:auto-->",
            source,
            re.S,
        )
        if inline_blocks:
            check(
                len(inline_blocks) == len(expected_inline_visuals.get(relative, ())),
                f"{relative}: inline visual is not explicitly approved",
                failures,
            )
            check(
                source.count("<!--inline-visual:auto-->") == len(inline_blocks)
                and source.count("<!--/inline-visual:auto-->") == len(inline_blocks),
                f"{relative}: inline visual markers are not balanced",
                failures,
            )
            inline_sources: set[str] = set()
            lead_sources = {str(image.get("src") or "") for image in page.article_images}
            for block in inline_blocks:
                check(
                    block.count("article-inline-visual") >= 1
                    and "article-inline-caption" in block
                    and "article-inline-credit" in block,
                    f"{relative}: inline visual lacks figure, caption, or credit",
                    failures,
                )
                image_match = re.search(r"<img\b([^>]*)>", block, re.I | re.S)
                check(image_match is not None, f"{relative}: inline visual lacks image", failures)
                if image_match is None:
                    continue
                attrs = dict(re.findall(r'([:\w-]+)="([^"]*)"', image_match.group(1)))
                image_src = attrs.get("src", "")
                observed_inline_visuals.setdefault(relative, []).append(image_src)
                check(
                    image_src in expected_inline_visuals.get(relative, ()),
                    f"{relative}: inline visual differs from approved asset: {image_src}",
                    failures,
                )
                check(
                    attrs.get("class") == "article-inline-image"
                    and attrs.get("loading") == "lazy"
                    and attrs.get("decoding") == "async",
                    f"{relative}: inline image loading contract is invalid: {image_src}",
                    failures,
                )
                check(
                    bool(compact(attrs.get("alt", ""))),
                    f"{relative}: inline image lacks meaningful alt text: {image_src}",
                    failures,
                )
                check(
                    attrs.get("width", "").isdigit()
                    and attrs.get("height", "").isdigit()
                    and int(attrs.get("width", "0")) > 0
                    and int(attrs.get("height", "0")) > 0,
                    f"{relative}: inline image dimensions are invalid: {image_src}",
                    failures,
                )
                check(
                    image_src.startswith("/") and (ROOT / image_src.lstrip("/")).is_file(),
                    f"{relative}: inline image is missing: {image_src}",
                    failures,
                )
                check(
                    image_src not in inline_sources and image_src not in lead_sources,
                    f"{relative}: inline image duplicates another page image: {image_src}",
                    failures,
                )
                inline_sources.add(image_src)
                if image_src.endswith(".svg"):
                    check(
                        "article-inline-visual--diagram" in block
                        and "Schemat: FishPoint (materiał własny)" in block,
                        f"{relative}: owned inline diagram lacks its credit: {image_src}",
                        failures,
                    )
                else:
                    # Zdjęcia bez zewnętrznego źródła (własne, udostępnione przez
                    # czytelnika) podają autora i podstawę publikacji bez linku.
                    owned = any(
                        f"({name})" in block for name in seo_inject.UNSOURCED_LICENSES
                    )
                    check(
                        "article-inline-visual--photo" in block
                        and (owned or 'rel="license external noopener"' in block),
                        f"{relative}: inline photo lacks linked provenance: {image_src}",
                        failures,
                    )
                    if relative.startswith("lowiska/"):
                        check(
                            "nie przedstawia konkretnego łowiska w tym regionie" in block,
                            f"{relative}: regional inline photo lacks disclaimer",
                            failures,
                        )
        title = compact("".join(page.title_text))
        check(
            bool(title) and title == page.metadata.get("og:title") == page.metadata.get("twitter:title"),
            f"{relative}: title/OG/Twitter title mismatch",
            failures,
        )
        description = page.metadata.get("description")
        check(
            bool(description)
            and description == page.metadata.get("og:description") == page.metadata.get("twitter:description"),
            f"{relative}: description/OG/Twitter mismatch",
            failures,
        )
        levels = [int(level) for level, _ in page.headings]
        check(levels.count(1) == 1, f"{relative}: expected exactly one H1", failures)
        check(
            all(next_level <= level + 1 for level, next_level in zip(levels, levels[1:])),
            f"{relative}: heading hierarchy skips a level",
            failures,
        )
        h1 = compact(next((str(text) for level, text in page.headings if int(level) == 1), ""))
        blog_postings = []
        for raw_json in page.json_ld:
            try:
                document = json.loads(raw_json)
            except json.JSONDecodeError:
                continue
            for node in walk(document):
                if not isinstance(node, dict):
                    continue
                if node.get("@type") == "BlogPosting":
                    blog_postings.append(node)
                if node.get("@type") == "FAQPage":
                    faq_parity_pages += 1
                    visible = normalize(" ".join(page.main_text))
                    for question in node.get("mainEntity", []):
                        answer = normalize(str((question.get("acceptedAnswer") or {}).get("text", "")))
                        check(not answer or answer in visible,
                              f"{relative}: FAQ schema differs from visible answer", failures)
        check(len(blog_postings) <= 1, f"{relative}: duplicate BlogPosting entity", failures)
        for posting in blog_postings:
            check(compact(str(posting.get("headline", ""))) == h1,
                  f"{relative}: BlogPosting headline differs from visible H1", failures)
            if relative in expected_about:
                observed_about = {
                    (str(node.get("@type")), str(node.get("name")))
                    for node in walk(posting.get("about"))
                    if isinstance(node, dict) and node.get("@type") and node.get("name")
                }
                check(
                    expected_about[relative] <= observed_about,
                    f"{relative}: missing evidence-backed method/place entities",
                    failures,
                )
        for raw_json in page.json_ld:
            try:
                json.loads(raw_json)
            except json.JSONDecodeError as error:
                failures.append(f"{relative}: invalid JSON-LD: {error}")

    check(visual_pages >= 73, "fewer than 73 articles have licensed lead visuals", failures)
    check(regional_visuals == 16, "all 16 regional fishery pages need illustrative visuals", failures)
    check(
        {key: sorted(value) for key, value in observed_inline_visuals.items()}
        == {key: sorted(value) for key, value in expected_inline_visuals.items()},
        "generated inline visuals differ from the explicit contextual allowlist",
        failures,
    )

    js_version = hashlib.md5((ROOT / "js/main.js").read_bytes()).hexdigest()[:8]
    for html_path in sorted(ROOT.rglob("*.html")):
        if ".git" in html_path.parts:
            continue
        relative = html_path.relative_to(ROOT).as_posix()
        source = html_path.read_text(encoding="utf-8", errors="replace")
        main_js_sources = [
            src for src in re.findall(r'<script\b[^>]*\bsrc=["\']([^"\']*)["\']', source, re.I)
            if urlparse(src).path.endswith("/js/main.js") or urlparse(src).path == "js/main.js"
        ]
        check(len(main_js_sources) == 1, f"{relative}: expected one local js/main.js reference", failures)
        if main_js_sources:
            check(
                urlparse(main_js_sources[0]).query == f"v={js_version}",
                f"{relative}: stale or malformed js/main.js version",
                failures,
            )
        page = parse(relative)
        for href in page.hrefs:
            target = local_link_target(html_path, href)
            if target is None:
                continue
            check(
                target.is_relative_to(ROOT) and target.is_file(),
                f"{relative}: missing local target for {href}",
                failures,
            )
        if "<!--content-advantage:auto-->" in source:
            check(
                page.content_advantage_count == 1,
                f"{relative}: expected exactly one content-advantage module",
                failures,
            )
            check(
                page.content_advantage_in_hero == 0,
                f"{relative}: content-advantage module is inside subpage hero",
                failures,
            )
            if relative not in {"index.html", "pierwsze-kroki/index.html"}:
                check(
                    page.content_advantage_in_article == 1,
                    f"{relative}: content-advantage module is outside article card",
                    failures,
                )
                check(
                    page.tldr_in_article >= 1,
                    f"{relative}: TLDR module is missing from article card",
                    failures,
                )

    # Menu prowadzi do wybranych wejść działu i do strony-huba; pełną listę
    # artykułów udostępnia hub. Powielanie całego działu w menu każdej podstrony
    # rozdymało powtarzalną nawigację ponad objętość samej treści.
    menu = parse("index.html")
    nav_sections = ("pierwsze-kroki", "sprzet", "techniki", "ryby", "lowiska", "poradniki")
    check(len(menu.submenu_links) == len(nav_sections),
          "navigation needs one submenu per main section", failures)
    for section, links in zip(nav_sections, menu.submenu_links):
        actual_targets = {
            local_link_target(ROOT / "index.html", href)
            for href in links
        }
        check(bool(actual_targets), f"navigation has no entries for {section}", failures)
        check((ROOT / section / "index.html").resolve() in actual_targets,
              f"navigation omits section hub for {section}", failures)

    # Każdy artykuł działu musi być osiągalny ze strony-huba tego działu.
    for section in nav_sections:
        hub = parse(f"{section}/index.html")
        hub_targets = {
            local_link_target(ROOT / section / "index.html", href)
            for href in hub.hrefs
        }
        expected_targets = {
            (ROOT / local_path(url)).resolve()
            for url in urls
            if Path(local_path(url)).parts[0] == section
            and not urlparse(url).path.endswith("/")
        }
        missing = expected_targets - hub_targets
        check(not missing, f"section hub {section} omits {len(missing)} pages", failures)
    hub_paths = {
        "pierwsze-kroki/index.html", "sprzet/index.html", "techniki/index.html",
        "ryby/index.html", "poradniki/index.html", "narzedzia/index.html",
        "lowiska/index.html", "forum/index.html", "aktualnosci/index.html",
        "kuchnia/index.html",
        "zgodnie-z-zasadami.html",
    }
    menu_targets = {
        local_link_target(ROOT / "index.html", href)
        for href in menu.hrefs
    }
    for hub in hub_paths:
        check((ROOT / hub).resolve() in menu_targets, f"navigation omits hub: {hub}", failures)

    news = parse("aktualnosci/index.html")
    expected_news_cards = {
        path.resolve()
        for path in (ROOT / "aktualnosci").glob("*.html")
        if path.name != "index.html"
    }
    news_card_targets = [
        local_link_target(ROOT / "aktualnosci/index.html", href)
        for _category, hrefs in news.news_cards
        for href in hrefs
    ]
    expected_news_categories = {
        "najnowsze", "rekordy", "srodowisko", "sezon", "poradniki",
        "sprzet", "pierwsze-kroki", "zawody", "relacje",
    }
    check(
        {category for category, _hrefs in news.news_cards} == expected_news_categories,
        "news index category sections are incomplete",
        failures,
    )
    check(
        len(news_card_targets) == len(set(news_card_targets)),
        "news index contains duplicate article cards",
        failures,
    )
    check(
        set(news_card_targets) == expected_news_cards,
        "news index must contain every article exactly once",
        failures,
    )
    home_news_targets = [
        local_link_target(ROOT / "index.html", href)
        for _category, hrefs in menu.news_cards
        for href in hrefs
    ]
    latest_news_targets = [
        local_link_target(ROOT / "aktualnosci/index.html", href)
        for category, hrefs in news.news_cards
        if category == "najnowsze"
        for href in hrefs
    ][:6]
    check(
        len(home_news_targets) == 6,
        "homepage must contain exactly six latest news cards",
        failures,
    )
    check(
        home_news_targets == latest_news_targets,
        "homepage news cards must match the six newest article cards in order",
        failures,
    )

    indexed_paths = {
        (ROOT / local_path(url)).resolve(): url
        for url in urls
    }
    contextual_inlinks = {path: 0 for path in indexed_paths}
    for url, page in parsed.items():
        source = (ROOT / local_path(url)).resolve()
        for href in page.contextual_hrefs:
            target = local_link_target(source, href)
            if target in contextual_inlinks and target != source:
                contextual_inlinks[target] += 1
    for target, count in contextual_inlinks.items():
        check(count > 0, f"{target.relative_to(ROOT)}: missing contextual inlink", failures)

    for html_path in sorted(ROOT.rglob("*.html")):
        if ".git" in html_path.parts:
            continue
        relative = html_path.relative_to(ROOT).as_posix()
        page = parse(relative)
        check(len(page.ids) == len(set(page.ids)), f"{relative}: duplicate HTML id", failures)
        for href in page.toc_hrefs:
            anchor = urlparse(href).fragment
            check(bool(anchor) and anchor in page.ids,
                  f"{relative}: TOC anchor does not exist: {href}", failures)
        for table in page.tables:
            check(table["captions"] == 1, f"{relative}: table needs exactly one caption", failures)
            check(table["th"] == table["scoped_th"],
                  f"{relative}: every table header needs scope", failures)

    llms_urls = {}
    for artifact in ("llms.txt", "llms-full.txt"):
        content = read(artifact)
        for marker in (
            "> Język: pl-PL.", "> Autor/redakcja:", "> Zakres:",
            "> Najnowsza merytoryczna zmiana:", "> Polityka źródeł i korekt:",
            "> Kanoniczny URL:",
        ):
            check(marker in content, f"{artifact}: missing llms metadata {marker}", failures)
        if artifact == "llms.txt":
            found = set(re.findall(
                r"^- \[[^\]]+\]\((https://fish-point\.pl/[^\s)]*)\):",
                content,
                re.M,
            ))
        else:
            found = set(re.findall(
                r"^Canonical URL: (https://fish-point\.pl/[^\s]*)$",
                content,
                re.M,
            ))
        llms_urls[artifact] = found
        check(found == set(urls), f"{artifact}: URLs differ from indexable sitemap", failures)

    for url, page in parsed.items():
        relative = local_path(url)
        if not relative.endswith("/index.html"):
            continue
        section_dir = (ROOT / relative).parent
        child_dates = []
        for child in sorted(section_dir.glob("*.html")):
            if child.name == "index.html":
                continue
            match = re.search(r"content-meta:\s*published=\d{4}-\d{2}-\d{2};\s*modified=(\d{4}-\d{2}-\d{2})", child.read_text(encoding="utf-8"))
            if match:
                child_dates.append(match.group(1))
        if not child_dates:
            continue
        expected = max(child_dates)
        visible_dates = re.findall(r"<time\b[^>]*\bdatetime=[\"']([^\"']+)", read(relative))
        collection_dates = [
            node.get("dateModified") for raw in page.json_ld
            for node in walk(json.loads(raw))
            if isinstance(node, dict) and node.get("@type") == "CollectionPage"
        ]
        check(expected in visible_dates, f"{relative}: visible hub freshness is stale", failures)
        check(collection_dates == [expected],
              f"{relative}: CollectionPage dateModified is not max child date", failures)

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

    # Kalendarz brań podaje wymiary i terminy ochronne — czytelnik musi móc
    # sprawdzić je w akcie, tak samo jak na karcie gatunku w atlasie.
    species_calendars = sorted((ROOT / "poradniki").glob("kalendarz-bran-*.html"))
    check(len(species_calendars) >= 10, "species catch calendars are missing", failures)
    for calendar_page in species_calendars:
        relative = calendar_page.relative_to(ROOT).as_posix()
        source = calendar_page.read_text(encoding="utf-8", errors="replace")
        block = re.search(
            r"<!--calendar-legal:auto-->(.*?)<!--/calendar-legal:auto-->", source, re.S
        )
        check(bool(block), f"{relative}: legal card is missing", failures)
        if block:
            check(
                source.count("<!--calendar-legal:auto-->") == 1
                and "fish-legal-current" in block.group(1)
                and "eli.gov.pl/api/acts/DU/2023/1373" in block.group(1),
                f"{relative}: legal card does not cite the current act",
                failures,
            )

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
            # Sam identyfikator gatunku nie wystarczy — IUCN zwraca wtedy 404.
            # Poprawny adres ma postać /species/<gatunek>/<ocena>.
            check(re.search(r"/species/\d+/\d+", href) is not None,
                  f"{fish_page.relative_to(ROOT)}: adres IUCN bez identyfikatora "
                  f"oceny (404): {href}",
                  failures)

    for family in ("tematy", "kuchnia", "aktualnosci"):
        metadata = json.loads(read(f"assets/img/{family}/_meta.json"))
        for key, record in metadata.items():
            filename = record.get("file")
            check(bool(filename), f"{family}/{key}: attribution record lacks file", failures)
            if filename:
                check((ROOT / "assets" / "img" / family / filename).is_file(), f"{family}/{key}: missing {filename}", failures)

    for source_page, image_path in tool_image_map().items():
        image = ROOT / image_path.lstrip("/")
        check(image.is_file(), f"{source_page}: TOOL_IMG asset is missing: {image_path}", failures)
        if image.is_file():
            check(image_width(image) >= 1200,
                  f"{source_page}: TOOL_IMG asset is narrower than 1200 px: {image_path}",
                  failures)

    check("(klasyczna." not in read("kuchnia/smazony-okon-sandacz.html"), "truncated recipe description remains", failures)

    # Data widoczna dla wyszukiwarki musi zgadzać się z trwałym content-meta.
    # Wcześniej stała tu ręcznie utrzymywana lista 14 stron z oczekiwanymi
    # datami; utrwalała błąd (np. jak-lowic-lina.html miało zaklepane
    # 2026-07-20, choć tekst zmieniono 2026-08-05). Kontrakt jest teraz
    # wyprowadzany z treści i obejmuje wszystkie strony.
    for page in sorted(ROOT.glob("**/*.html")):
        if any(part.startswith(".") for part in page.relative_to(ROOT).parts):
            continue
        html = page.read_text(encoding="utf-8")
        meta = re.search(r"content-meta:[^\n>]*modified=(\d{4}-\d{2}-\d{2})", html)
        if not meta:
            continue
        relative = page.relative_to(ROOT).as_posix()
        published = re.search(r"content-meta:\s*published=(\d{4}-\d{2}-\d{2})", html)
        check(published is not None and published.group(1) <= meta.group(1),
              f"{relative}: modified jest wcześniejsze niż published", failures)
        emitted = re.search(r'article:modified_time" content="(\d{4}-\d{2}-\d{2})', html)
        if emitted:
            check(emitted.group(1) == meta.group(1),
                  f"{relative}: article:modified_time ({emitted.group(1)}) "
                  f"rozjeżdża się z content-meta ({meta.group(1)})",
                  failures)

    feed = ET.fromstring(read("feed.xml"))
    for item in feed.findall("./channel/item"):
        link = item.findtext("link", "")
        title = compact(item.findtext("title", ""))
        relative = local_path(link)
        if (ROOT / relative).is_file():
            page = parse(relative)
            h1 = compact(next((str(text) for level, text in page.headings if int(level) == 1), ""))
            check(title == h1, f"{relative}: RSS title differs from visible H1", failures)

    # Hub atlasu obiecuje w tytule i opisie konkretną liczbę gatunków. Liczba
    # rozjechała się już raz (30 wobec 40 kart), a widać ją w wynikach
    # wyszukiwania — niech pilnuje jej kontrakt, nie pamięć.
    # W katalogu ryby/ leżą też strony tematyczne (np. chronione.html), które
    # nie są kartami gatunku i nie mogą zawyżać deklarowanej liczby.
    atlas_non_cards = {"index.html", "chronione.html"}
    atlas_cards = len([p for p in (ROOT / "ryby").glob("*.html") if p.name not in atlas_non_cards])
    atlas_html = read("ryby/index.html")
    for claim in re.findall(r"Atlas (\d+) gatunków", atlas_html):
        check(int(claim) == atlas_cards,
              f"ryby/index.html: opis obiecuje {claim} gatunków, kart jest {atlas_cards}",
              failures)
    for claim in re.findall(r"<title>[^<]*?(\d+) gatunków", atlas_html):
        check(int(claim) == atlas_cards,
              f"ryby/index.html: tytuł obiecuje {claim} gatunków, kart jest {atlas_cards}",
              failures)

    full_llms = read("llms-full.txt")
    for marker in ("Canonical URL:", "Author:", "Published:", "Modified:", "Type:", "Sources:"):
        check(marker in full_llms, f"llms-full.txt: missing document provenance {marker}", failures)

    # Strony o stanie prawnym niosą rok obowiązywania w tytule, opisie i H1,
    # bo tak brzmią realne zapytania („okresy ochronne ryb 2024", „karta
    # wędkarska 2026" — Google Trends, sierpień 2026). Rok musi być bieżący;
    # seo_inject podnosi go przy każdej przebudowie, a ten kontrakt pilnuje,
    # żeby strona nie została z zeszłorocznym.
    current_year = str(datetime.date.today().year)
    for relative in sorted(seo_inject.LEGAL_YEAR_PAGES):
        html = read(relative)
        for label, pattern in (
            ("tytuł", r"<title>(.*?)</title>"),
            ("opis", r'<meta\s+name="description"\s+content="([^"]*)"'),
            ("H1", r"<h1\b[^>]*>(.*?)</h1>"),
        ):
            found = re.search(pattern, html, re.S)
            check(found is not None, f"{relative}: brak elementu {label}", failures)
            if not found:
                continue
            text = seo_inject.LEGAL_CITATION_YEAR_RE.sub("", found.group(1))
            years = set(re.findall(r"\b20\d{2}\b", text))
            check(years == {current_year},
                  f"{relative}: {label} niesie rok {sorted(years) or 'brak'}, "
                  f"oczekiwano {current_year}",
                  failures)

    # Macierz gatunek × miesiąc oznacza miesiące bez wiersza w karcie gatunkowej
    # jako okres ochronny. To wniosek z nieobecności, więc musi zgadzać się
    # z rejestrem prawnym — inaczej tabela powiedziałaby „łów", gdy trwa ochrona.
    months_pl = [m.capitalize() for m in seo_inject.CALENDAR_MONTHS_PL]
    month_number = {name: i for i, name in enumerate(months_pl, start=1)}
    # Rejestr zapisuje okres raz jako „okres ochronny", raz jako samo „okres"
    # (pstrąg, gdzie koniec zależy od odcinka) — wzorzec musi objąć obie formy.
    protection_re = re.compile(
        r"okres(?: ochronny)? (\d{1,2}) (\w+)[–-](\d{1,2}) (\w+)", re.I)
    genitive = {
        "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5,
        "czerwca": 6, "lipca": 7, "sierpnia": 8, "września": 9,
        "października": 10, "listopada": 11, "grudnia": 12,
    }
    for slug, _name in seo_inject.CALENDAR_MATRIX_SPECIES:
        relative = f"poradniki/kalendarz-bran-{slug}.html"
        if not (ROOT / relative).is_file():
            continue
        table = re.search(r'<table class="tool-table">.*?</table>',
                          read(relative), re.S)
        check(table is not None, f"{relative}: brak tabeli miesięcznej", failures)
        if not table:
            continue
        listed = {
            m.strip() for m in
            re.findall(r'<th scope="row">([^<]+)</th>', table.group(0))}
        silent = {month_number[m] for m in months_pl if m not in listed}
        summary = seo_inject.FISH_LEGAL_SUMMARIES.get(slug, "")
        found = protection_re.search(summary)
        if not found:
            # Bez krajowego okresu ochronnego karta musi opisywać wszystkie
            # dwanaście miesięcy — inaczej macierz wymyśli ochronę, której nie ma.
            check(not silent,
                  f"{relative}: brak miesięcy {sorted(silent)}, a rejestr prawny "
                  "nie podaje krajowego okresu ochronnego",
                  failures)
            continue
        start, end = genitive[found.group(2).lower()], genitive[found.group(4).lower()]
        legal = (set(range(start, end + 1)) if start <= end
                 else set(range(start, 13)) | set(range(1, end + 1)))
        check(silent <= legal,
              f"{relative}: miesiące {sorted(silent - legal)} nie mają wiersza, "
              f"choć rejestr prawny nie obejmuje ich ochroną ({summary[:60]})",
              failures)

    # Duże obrazy muszą mieć warianty mobilne i uczciwe deskryptory szerokości.
    # Audyt z 9 sierpnia 2026: warianty istniały dla jednego obrazu, więc telefon
    # pobierał grafiki 1600 px przy widoku 390 px (81% ruchu to mobile).
    missing_variants, lying_descriptors = [], []
    for page in sorted(ROOT.glob("**/*.html")):
        if any(part.startswith(".") for part in page.relative_to(ROOT).parts):
            continue
        html = page.read_text(encoding="utf-8")
        for src in re.findall(r'<img\b[^>]+class="article-image"[^>]*src="([^"]+)"', html):
            if src.startswith(("http", "data:")):
                continue
            disk = Path(os.path.normpath(page.parent / src))
            if not disk.is_file():
                continue
            width = image_width(disk)
            if not width or width < 960:
                continue
            stem, suffix = os.path.splitext(str(disk))
            if not all(Path(f"{stem}-{w}{suffix}{fmt}").is_file()
                       for w in (640, 960) for fmt in ("", ".avif", ".webp")):
                missing_variants.append(f"{page.relative_to(ROOT).as_posix()} → {src}")
        for descriptor_src, declared in re.findall(
                r'srcset="[^"]*?([^ ",]+\.jpg(?:\.avif|\.webp)?) (\d+)w"', html):
            base = descriptor_src.split("/")[-1].replace(".avif", "").replace(".webp", "")
            if re.search(r"-(640|960)\.jpg$", base):
                continue
            disk = next((p for p in ROOT.glob(f"assets/img/**/{base}")), None)
            if disk and (actual := image_width(disk)) and abs(actual - int(declared)) > 1:
                lying_descriptors.append(f"{base}: deklaruje {declared}w, ma {actual}px")
    check(not missing_variants,
          f"duże obrazy bez wariantów mobilnych: {missing_variants[:5]}", failures)
    check(not lying_descriptors,
          f"deskryptor srcset nie zgadza się z plikiem: {lying_descriptors[:5]}", failures)

    # Data aktualizacji musi śledzić treść, a nie moment przebudowy.
    # Audyt z 9 sierpnia 2026: 104 z 201 stron deklarowały lastmod 2026-07-20,
    # mimo realnych zmian redakcyjnych z 5–8 sierpnia, bo content-meta było
    # zapisywane raz i nigdy nie odświeżane.
    stale, missing_fp = [], []
    for page in sorted(ROOT.glob("**/*.html")):
        if any(part.startswith(".") for part in page.relative_to(ROOT).parts):
            continue
        src = page.read_text(encoding="utf-8")
        match = seo_inject.CONTENT_META_RE.search(src)
        if not match:
            continue
        rel = page.relative_to(ROOT).as_posix()
        if match.group(3) is None:
            missing_fp.append(rel)
        elif match.group(3) != seo_inject.editorial_fingerprint(src):
            stale.append(rel)
    check(not missing_fp,
          f"content-meta bez odcisku treści (fp=): {missing_fp[:5]}", failures)
    check(not stale,
          f"data aktualizacji rozjechała się z treścią: {stale[:5]}", failures)

    # Dz.U. 2023 poz. 1373 to samodzielne rozporządzenie MRiRW z 12 lipca 2023 r.
    # „w sprawie szczegółowych warunków ochrony i połowu ryb w powierzchniowych
    # wodach śródlądowych”. Uchyliło ono akt „w sprawie połowu ryb oraz warunków
    # chowu, hodowli i połowu innych organizmów żyjących w wodzie”, więc ten tytuł
    # nie może wracać jako nazwa obowiązującej podstawy prawnej.
    repealed_title = "połowu ryb oraz warunków chowu, hodowli i połowu innych organizmów"
    wrong_basis = [
        page.relative_to(ROOT).as_posix()
        for page in sorted(ROOT.glob("**/*.html"))
        # Rejestr korekt musi zacytować wcześniejsze, błędne brzmienie.
        if page.relative_to(ROOT).as_posix() != "korekty.html"
        and not any(part.startswith(".") for part in page.relative_to(ROOT).parts)
        and repealed_title in compact(page.read_text(encoding="utf-8"))
    ]
    check(not wrong_basis,
          f"tytuł uchylonego rozporządzenia jako podstawa prawna: {wrong_basis[:5]}", failures)

    # Zabezpieczenie przed powrotem masowej daty: żadna pojedyncza data nie
    # może obejmować więcej niż 40% stron w sitemapie.
    lastmods = [e.text for e in sitemap.iter(f"{{{SITEMAP_NS['s']}}}lastmod") if e.text]
    if lastmods:
        top_date, top_count = Counter(d[:10] for d in lastmods).most_common(1)[0]
        check(top_count <= len(lastmods) * 0.4,
              f"masowa data w sitemapie: {top_date} na {top_count} z {len(lastmods)} stron",
              failures)
    if failures:
        print("Audit contracts failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Audit contracts: ok ({len(urls)} sitemap pages; {faq_parity_pages} FAQ parity checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
