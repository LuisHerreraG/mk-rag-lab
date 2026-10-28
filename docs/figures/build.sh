#!/usr/bin/env bash
# Regenera las figuras desde HTML con Chrome headless (sin dependencias nuevas).
#   ./docs/figures/build.sh
set -euo pipefail
cd "$(dirname "$0")"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
[ -x "$CHROME" ] || { echo "falta Chrome: exportá CHROME=/ruta/al/chrome" >&2; exit 1; }

# la salida real que se muestra en demo.html (recortada a propósito)
PYTHONPATH=../../src ../../.venv/bin/python -m mk_rag_lab.rag --repl 2>/dev/null <<'IN' > demo-output.txt || true
¿por qué se usa solapamiento entre fragmentos?
¿cuál es la capital de Honduras?
salir
IN

for pair in "architecture 1200 430" "demo 1200 620" "metrics 1200 430"; do
  set -- $pair
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
    --window-size="$2,$3" --screenshot="$PWD/$1.png" "$PWD/$1.html" >/dev/null 2>&1
  echo "  $1.png"
done
