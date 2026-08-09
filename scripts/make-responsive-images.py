#!/usr/bin/env python3
"""Generuje mobilne warianty szerokości dla obrazów artykułów.

optimize_images.py potrafi zbudować pełny `srcset`, ale tylko wtedy, gdy obok
oryginału leżą pliki `X-640.jpg{,.avif,.webp}` i `X-960.jpg{,.avif,.webp}`.
Przed sierpniem 2026 istniały one dla jednego obrazu, więc telefon pobierał
grafikę w pełnej rozdzielczości (np. 1600 px przy widoku 390 px).

Skrypt jest idempotentny: pomija warianty, które już są, i nie tyka obrazów
węższych niż najbliższy próg.
"""
from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (640, 960)
# Poniżej tej szerokości wariant mobilny nie ma sensu — obraz i tak jest mały.
MIN_SOURCE_WIDTH = 960

# ImageMagick 7 udostępnia `magick`, ImageMagick 6 (m.in. w obrazach Ubuntu
# używanych przez GitHub Actions) tylko `convert`. Obsługujemy obie wersje.
MAGICK = shutil.which("magick")
CONVERT = [MAGICK] if MAGICK else ([shutil.which("convert")]
                                   if shutil.which("convert") else None)
AVIFENC = shutil.which("avifenc")


def image_width(path: Path) -> int | None:
    """Szerokość JPEG czytana z nagłówka — bez zależności zewnętrznych."""
    try:
        with open(path, "rb") as handle:
            if handle.read(2) != b"\xff\xd8":
                return None
            while True:
                byte = handle.read(1)
                while byte and byte != b"\xff":
                    byte = handle.read(1)
                while byte == b"\xff":
                    byte = handle.read(1)
                if not byte:
                    return None
                marker = byte[0]
                length = struct.unpack(">H", handle.read(2))[0]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                    handle.read(1)
                    _height, width = struct.unpack(">HH", handle.read(4))
                    return width
                handle.seek(length - 2, 1)
    except Exception:
        return None


def used_images() -> set[Path]:
    """Obrazy realnie osadzone w treści stron."""
    found: set[Path] = set()
    for page in ROOT.glob("**/*.html"):
        if any(part.startswith(".") for part in page.relative_to(ROOT).parts):
            continue
        html = page.read_text(encoding="utf-8", errors="replace")
        for src in re.findall(r'<img\b[^>]+src="([^"]+)"', html):
            if src.startswith(("http", "data:")):
                continue
            if re.search(r"-(?:640|960)\.", src):
                continue
            disk = (ROOT / src.lstrip("/")) if src.startswith("/") \
                else (page.parent / src)
            disk = Path(os.path.normpath(disk))
            if disk.is_file() and disk.suffix.lower() in (".jpg", ".jpeg", ".png"):
                found.add(disk)
    return found


def run(cmd: list[str]) -> bool:
    return subprocess.run(cmd, capture_output=True).returncode == 0


def build_variant(src: Path, width: int) -> list[str]:
    """Tworzy brakujące pliki jednego wariantu. Zwraca listę utworzonych."""
    made = []
    stem, suffix = os.path.splitext(str(src))
    base = Path(f"{stem}-{width}{suffix}")
    if not base.exists():
        if not run(CONVERT + ["-limit", "memory", "256MiB", str(src),
                              "-resize", f"{width}x>", "-strip",
                              "-quality", "82", str(base)]):
            return made
        made.append(base.name)
    targets = [(".webp", CONVERT + ["-limit", "memory", "256MiB", str(base),
                                    "-quality", "80", f"{base}.webp"])]
    if AVIFENC:
        targets.append((".avif", [AVIFENC, "-q", "55", "--speed", "6",
                                  str(base), f"{base}.avif"]))
    else:
        targets.append((".avif", CONVERT + ["-limit", "memory", "256MiB",
                                            str(base), "-quality", "55",
                                            f"{base}.avif"]))
    for fmt, cmd in targets:
        target = Path(f"{base}{fmt}")
        if not target.exists():
            if run(cmd):
                made.append(target.name)
    return made


def main() -> int:
    if CONVERT is None:
        # Warianty są wersjonowane w repozytorium, więc brak ImageMagick nie
        # może wywrócić wdrożenia. Braki dla nowo dodanych obrazów wyłapie
        # kontrakt „duże obrazy bez wariantów mobilnych" w audit-contracts.py.
        print("ImageMagick niedostępny — pomijam generowanie wariantów.",
              file=sys.stderr)
        return 0

    only = sys.argv[1:] or None
    images = sorted(used_images())
    if only:
        images = [p for p in images if any(o in str(p) for o in only)]
    print(f"obrazów w treści: {len(images)}")

    created, skipped, too_small = 0, 0, 0
    for img in images:
        w = image_width(img)
        if w is None:
            continue
        if w < MIN_SOURCE_WIDTH:
            too_small += 1
            continue
        for width in WIDTHS:
            if width >= w:
                continue
            made = build_variant(img, width)
            created += len(made)
            if not made:
                skipped += 1
    print(f"utworzone pliki: {created}")
    print(f"warianty już obecne: {skipped}")
    print(f"obrazy poniżej {MIN_SOURCE_WIDTH} px (pominięte): {too_small}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
