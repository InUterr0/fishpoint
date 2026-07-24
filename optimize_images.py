#!/usr/bin/env python3
"""Owija <img src="...jpg"> w <picture> z wariantami AVIF/WebP, gdy pliki
obok istnieją (X.jpg.avif, X.jpg.webp). Przeglądarka pobiera lżejszy format,
co poprawia LCP/Core Web Vitals. JPG zostaje jako fallback.

Jeżeli obok obrazu istnieją także X-640.jpg.{avif,webp} i
X-960.jpg.{avif,webp}, warianty dostają deskryptory szerokości. Takie pliki
powinny zachowywać proporcje oryginału; atrybuty width/height na <img> zostają
bez zmian, więc nie wprowadzamy CLS.

Idempotentny: najpierw rozpakowuje wcześniej dodane <picture class="opt">,
potem pakuje na nowo. Uruchamiaj po seo_inject.py: python3 optimize_images.py
"""
import os, re

ROOT = os.path.dirname(os.path.abspath(__file__))

# <picture class="opt"> ... <img ...> </picture>  -> z powrotem sam <img ...>
unwrap_re = re.compile(r'<picture class="opt">(?:<source[^>]*>)*(<img\b[^>]*?>)</picture>', re.S)
img_re = re.compile(r'<img\b[^>]*?src="([^"]+\.jpg)"[^>]*?>', re.S)


def resolve(src, page_dir):
    """Ścieżka pliku na dysku dla src z HTML (/, ../, bare)."""
    if src.startswith("http"):
        return None
    if src.startswith("/"):
        return os.path.join(ROOT, src.lstrip("/"))
    return os.path.normpath(os.path.join(page_dir, src))


def responsive_srcset(src, disk, fmt, declared_width):
    """Zwraca srcset dla dostępnych wariantów mobilnych jednego formatu."""
    stem, suffix = os.path.splitext(src)
    disk_stem, disk_suffix = os.path.splitext(disk)
    candidates = []
    for width in (640, 960):
        variant = f"{stem}-{width}{suffix}"
        if os.path.exists(f"{disk_stem}-{width}{disk_suffix}{fmt}"):
            candidates.append(f"{variant}{fmt} {width}w")
    candidates.append(f"{src}{fmt} {declared_width}w")
    return ", ".join(candidates)


def responsive_fallback(tag, src, declared_width):
    """Dodaje oznaczone srcset/sizes do fallbacku JPG bez zmiany wymiarów."""
    stem, suffix = os.path.splitext(src)
    srcset = ", ".join(
        f"{stem}-{width}{suffix} {width}w" for width in (640, 960)
    ) + f", {src} {declared_width}w"
    attrs = f' data-responsive-fallback="true" srcset="{srcset}" sizes="(max-width: 700px) 100vw, 1200px"'
    return re.sub(r"\s*/?>$", f"{attrs} />", tag)


def process(path):
    with open(path, encoding="utf-8") as f:
        src_html = f.read()
    page_dir = os.path.dirname(path)
    # 1) rozpakuj poprzednie owinięcia (idempotencja)
    src_html = unwrap_re.sub(r"\1", src_html)

    # 2) owiń na nowo tam, gdzie są warianty
    def repl(m):
        tag = m.group(0)
        tag = re.sub(
            r'\sdata-responsive-fallback="true"\s+srcset="[^"]*"\s+sizes="[^"]*"',
            "",
            tag,
        )
        src = m.group(1)
        disk = resolve(src, page_dir)
        if not disk:
            return tag
        if os.path.exists(disk + ".avif") and os.path.exists(disk + ".webp"):
            width = re.search(r'\bwidth\s*=\s*["\'](\d+)["\']', tag, re.I)
            mobile_variants = width and all(
                os.path.exists(f"{os.path.splitext(disk)[0]}-{mobile}{os.path.splitext(disk)[1]}{fmt}")
                for mobile in (640, 960)
                for fmt in ("", ".avif", ".webp")
            )
            if mobile_variants:
                declared_width = width.group(1)
                sizes = '(max-width: 700px) 100vw, 1200px'
                return (
                    '<picture class="opt">'
                    f'<source srcset="{responsive_srcset(src, disk, ".avif", declared_width)}" '
                    f'sizes="{sizes}" type="image/avif">'
                    f'<source srcset="{responsive_srcset(src, disk, ".webp", declared_width)}" '
                    f'sizes="{sizes}" type="image/webp">'
                    f"{responsive_fallback(tag, src, declared_width)}</picture>"
                )
            return (
                '<picture class="opt">'
                f'<source srcset="{src}.avif" type="image/avif">'
                f'<source srcset="{src}.webp" type="image/webp">'
                f"{tag}</picture>"
            )
        return tag

    new_html = img_re.sub(repl, src_html)
    if new_html != src_html:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_html)
        return True
    return False


def main():
    changed = 0
    total = 0
    for dirpath, _, files in os.walk(ROOT):
        if "/.git" in dirpath:
            continue
        for fn in files:
            if fn.endswith(".html") and fn != "404.html":
                total += 1
                if process(os.path.join(dirpath, fn)):
                    changed += 1
    print(f"optimize_images: zaktualizowano {changed}/{total} stron (AVIF/WebP <picture>)")


if __name__ == "__main__":
    main()
