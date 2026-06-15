#!/usr/bin/env python3
"""Dodaje atrybuty width/height do wszystkich <img> (eliminacja CLS).
Wymiary odczytywane raz na plik graficzny przez `magick identify`.
Idempotentny: pomija <img>, które już mają width."""
import os, re, glob, subprocess, json

ROOT = os.path.dirname(os.path.abspath(__file__))
cache = {}


def dims(fs_path):
    if fs_path in cache:
        return cache[fs_path]
    if not os.path.isfile(fs_path):
        cache[fs_path] = None
        return None
    try:
        out = subprocess.check_output(
            ["magick", "identify", "-format", "%w %h", fs_path],
            stderr=subprocess.DEVNULL, text=True,
        ).strip().split()
        cache[fs_path] = (out[0], out[1]) if len(out) == 2 else None
    except Exception:
        cache[fs_path] = None
    return cache[fs_path]


img_tag = re.compile(r"<img\b[^>]*?>", re.S)
src_re = re.compile(r'src="([^"]+)"')

changed_files = 0
changed_imgs = 0
for p in glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True):
    src = open(p, encoding="utf-8").read()
    page_dir = os.path.dirname(p)
    file_changed = False

    def repl(m):
        global changed_imgs, file_changed
        tag = m.group(0)
        if re.search(r"\bwidth=", tag):
            return tag
        sm = src_re.search(tag)
        if not sm:
            return tag
        s = sm.group(1)
        if s.startswith("http") or s.startswith("data:"):
            return tag
        fs = os.path.normpath(os.path.join(page_dir, s))
        d = dims(fs)
        if not d:
            return tag
        w, h = d
        self_closing = tag.rstrip().endswith("/>")
        inner = tag.rstrip()
        inner = inner[:-2] if self_closing else inner[:-1]  # usuń "/>" lub ">"
        inner = inner.rstrip()
        end = " />" if self_closing else ">"
        new_tag = f'{inner} width="{w}" height="{h}"{end}'
        changed_imgs += 1
        file_changed = True
        return new_tag

    new_src = img_tag.sub(repl, src)
    if file_changed:
        open(p, "w", encoding="utf-8").write(new_src)
        changed_files += 1

print(f"Pliki zmienione: {changed_files}, obrazki z wymiarami: {changed_imgs}")
print(f"Unikalne pliki graficzne odczytane: {sum(1 for v in cache.values() if v)}")
missing = [k for k, v in cache.items() if v is None]
if missing:
    print("BRAK pliku/odczytu dla:", *[os.path.relpath(m, ROOT) for m in missing], sep="\n  ")
