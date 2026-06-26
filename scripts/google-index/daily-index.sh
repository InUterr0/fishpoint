#!/usr/bin/env bash
# Codzienny automat /indexuj: zgłasza najnowsze artykuły do indeksowania w GSC
# i dopisuje raport do ~/projekty/raporty/indexuj-raport.md.
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:/home/baniak/.local/bin:$PATH"
PROJ="/home/baniak/projekty/strona wędkarstwo"
REPORTS="/home/baniak/projekty/raporty"
mkdir -p "$REPORTS"
cd "$PROJ" || exit 1
TS="$(date '+%Y-%m-%d %H:%M')"
OUT="$(node scripts/google-index/run.mjs "$@" 2>&1)"; RC=$?
SUMMARY="$(printf '%s\n' "$OUT" | grep -F '[gindex] DONE' | sed 's/\[gindex\] //')"
[ -z "$SUMMARY" ] && SUMMARY="(brak linii DONE — możliwy problem z przeglądarką/logowaniem; exit=$RC)"
{
  printf '## %s — /indexuj\n\n' "$TS"
  printf '**Podsumowanie:** %s\n\n' "$SUMMARY"
  printf '<details><summary>Pełny log</summary>\n\n```\n%s\n```\n</details>\n\n---\n\n' "$OUT"
} >> "$REPORTS/indexuj-raport.md"
