#!/usr/bin/env python3
"""Generuje search-index.json dla wyszukiwarki serwisu (szukaj.html).

Przechodzi po wszystkich stronach HTML, wyciąga tytuł, opis i sekcję,
zapisuje lekki indeks JSON przeszukiwany po stronie klienta. Uruchom po
dodaniu/zmianie treści:  python3 build_search.py
"""
import os, re, html, json

ROOT = os.path.dirname(os.path.abspath(__file__))
SECTIONS = {
    "ryby": "Atlas ryb", "poradniki": "Poradniki", "kuchnia": "Kuchnia",
    "aktualnosci": "Blog", "sprzet": "Sprzęt", "techniki": "Techniki",
    "pierwsze-kroki": "Pierwsze kroki", "narzedzia": "Narzędzia",
}
SKIP = {"404.html", "szukaj.html"}
title_re = re.compile(r"<title>(.*?)</title>", re.S)
desc_re = re.compile(r'<meta\s+name="description"\s+content="(.*?)"', re.S)


def rel_url(path):
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel


def main():
    items = []
    for dirpath, _, files in os.walk(ROOT):
        if "/.git" in dirpath or "/obrazy" in dirpath:
            continue
        for fn in files:
            if not fn.endswith(".html") or fn in SKIP:
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding="utf-8") as f:
                src = f.read()
            tm, dm = title_re.search(src), desc_re.search(src)
            if not tm or not dm:
                continue
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            parts = rel.split("/")
            section = SECTIONS.get(parts[0], "") if len(parts) > 1 else ""
            title = html.unescape(tm.group(1).strip()).split(" — ")[0].split(" - ")[0]
            desc = html.unescape(dm.group(1).strip())
            items.append({
                "t": title, "d": desc, "u": rel_url(path), "s": section,
            })
    items.sort(key=lambda x: (x["s"], x["t"]))
    out = os.path.join(ROOT, "search-index.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, separators=(",", ":"))
    print(f"search-index.json: {len(items)} stron")


if __name__ == "__main__":
    main()
