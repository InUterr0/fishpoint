#!/usr/bin/env python3
"""Focused regression contracts for the July 2026 FishPoint audit fixes."""

from __future__ import annotations

import hashlib
import ast
import struct

import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
INTERNAL_HOSTS = {"fish-point.pl", "www.fish-point.pl"}



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
    check(len(urls) == 197 and len(set(urls)) == 197, "sitemap must contain 197 unique URLs", failures)

    visual_pages = 0
    regional_visuals = 0
    expected_inline_visuals = {
        "pierwsze-kroki/jak-nabic-przynete-i-odhaczyc-rybe.html":
            "/assets/img/tematy/schemat-catch-release.svg",
        "techniki/spinning.html": "/assets/img/tematy/schemat-spinning.svg",
        "techniki/karpiowanie.html": "/assets/img/tematy/schemat-karpiowy.svg",
        "techniki/splawik.html": "/assets/img/tematy/schemat-splawik.svg",
        "techniki/feeder-dla-poczatkujacych.html": "/assets/img/tematy/schemat-feeder.svg",
        "poradniki/catch-and-release.html": "/assets/img/tematy/schemat-catch-release.svg",
        "poradniki/echosondy.html": "/assets/img/tematy/schemat-echosonda.svg",
        "poradniki/wezly-wedkarskie.html": "/assets/img/tematy/schemat-wezel.svg",
        "kuchnia/przygotowanie-ryby.html": "/assets/img/tematy/schemat-pakowanie.svg",
        "aktualnosci/zezwolenia-online-2026.html": "/assets/img/tematy/schemat-e-zezwolenie.svg",
        "aktualnosci/zakaz-polowu-bobr-lipiec-2026.html":
            "/assets/img/tematy/schemat-monitoring-wody.svg",
        "narzedzia/czy-moge-zabrac-rybe.html": "/assets/img/tematy/schemat-pomiar-ryby.svg",
    }
    observed_inline_visuals: dict[str, str] = {}
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
            check(page.article_license_links == 1,
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
                relative in expected_inline_visuals and len(inline_blocks) == 1,
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
                if len(inline_blocks) == 1:
                    observed_inline_visuals[relative] = image_src
                    check(
                        image_src == expected_inline_visuals.get(relative),
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
                    check(
                        "article-inline-visual--photo" in block
                        and 'rel="license external noopener"' in block,
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
        observed_inline_visuals == expected_inline_visuals,
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

    # Każdy główny dział pokazuje wszystkie indeksowalne artykuły; strony-huby
    # pozostają dostępne przez osobne linki „Zobacz cały dział”.
    menu = parse("index.html")
    nav_sections = ("pierwsze-kroki", "sprzet", "techniki", "ryby", "lowiska", "poradniki")
    check(len(menu.submenu_links) == len(nav_sections),
          "navigation needs one submenu per main section", failures)
    for section, links in zip(nav_sections, menu.submenu_links):
        actual_targets = {
            local_link_target(ROOT / "index.html", href)
            for href in links
        }
        expected_targets = {
            (ROOT / local_path(url)).resolve()
            for url in urls
            if Path(local_path(url)).parts[0] == section
            and not urlparse(url).path.endswith("/")
        }
        missing = expected_targets - actual_targets
        check(not missing, f"navigation omits {len(missing)} pages from {section}", failures)
    hub_paths = {
        "pierwsze-kroki/index.html", "sprzet/index.html", "techniki/index.html",
        "ryby/index.html", "poradniki/index.html", "narzedzia/index.html",
        "lowiska/index.html", "forum/index.html", "aktualnosci/index.html",
        "kuchnia/index.html", "humor/index.html", "zakupy.html",
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

    for source_page, image_path in tool_image_map().items():
        image = ROOT / image_path.lstrip("/")
        check(image.is_file(), f"{source_page}: TOOL_IMG asset is missing: {image_path}", failures)
        if image.is_file():
            check(image_width(image) >= 1200,
                  f"{source_page}: TOOL_IMG asset is narrower than 1200 px: {image_path}",
                  failures)

    check("2GekupS_N9s/hqdefault.jpg" not in read("humor/filmiki.html"), "known 404 video thumbnail remains", failures)
    check("(klasyczna." not in read("kuchnia/smazony-okon-sandacz.html"), "truncated recipe description remains", failures)

    modified_dates = {
        relative: "2026-07-17"
        for relative in (
            "narzedzia/czy-moge-zabrac-rybe.html",
            "pierwsze-kroki/index.html",
            "poradniki/index.html",
        )
    }
    modified_dates.update({
        "aktualnosci/jak-lowic-lina.html": "2026-07-20",
        "lowiska/index.html": "2026-07-20",
        "lowiska/pomorskie.html": "2026-07-20",
        "narzedzia/kalendarz-ksiezycowy.html": "2026-07-20",
        "ryby/leszcz.html": "2026-07-20",
        "ryby/ploc.html": "2026-07-20",
        "ryby/szczupak.html": "2026-07-20",
        "ryby/wegorz.html": "2026-07-20",
        "aktualnosci/przyneta-na-spinning.html": "2026-07-20",
        "pierwsze-kroki/pierwszy-zestaw-wedkarski-budzet.html": "2026-07-20",
        "pierwsze-kroki/twoj-pierwszy-wyjazd-na-ryby.html": "2026-07-20",
    })
    index_pages = {"lowiska/index.html", "pierwsze-kroki/index.html", "poradniki/index.html"}
    for relative, expected_modified in modified_dates.items():
        html = read(relative)
        check(
            re.search(rf"content-meta:[^\n]*modified={expected_modified}", html) is not None,
            f"{relative}: stale content-meta modified date",
            failures,
        )
        if relative not in index_pages:
            check(
                f'article:modified_time" content="{expected_modified}' in html,
                f"{relative}: stale generated modified time",
                failures,
            )

    feed = ET.fromstring(read("feed.xml"))
    for item in feed.findall("./channel/item"):
        link = item.findtext("link", "")
        title = compact(item.findtext("title", ""))
        relative = local_path(link)
        if (ROOT / relative).is_file():
            page = parse(relative)
            h1 = compact(next((str(text) for level, text in page.headings if int(level) == 1), ""))
            check(title == h1, f"{relative}: RSS title differs from visible H1", failures)

    full_llms = read("llms-full.txt")
    for marker in ("Canonical URL:", "Author:", "Published:", "Modified:", "Type:", "Sources:"):
        check(marker in full_llms, f"llms-full.txt: missing document provenance {marker}", failures)
    if failures:
        print("Audit contracts failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Audit contracts: ok ({len(urls)} sitemap pages; {faq_parity_pages} FAQ parity checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
