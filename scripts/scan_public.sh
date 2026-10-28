#!/usr/bin/env bash
# Escaneo previo a publicar: ¿el repo (árbol E HISTORIAL) revela algo que no debe?
#
#   ./scripts/scan_public.sh
#
# Sale 1 si encuentra algo. Correrlo SIEMPRE antes de `gh repo create --public`.
# Los patrones son deliberadamente amplios: un falso positivo se revisa en segundos,
# una filtración no se deshace.
set -uo pipefail
cd "$(dirname "$0")/.."

PATTERNS=(
  'https://[a-z0-9-]+\.openai\.azure\.com'      # endpoint real (no el placeholder)
  'https://[a-z0-9-]+\.search\.windows\.net'
  'mk-rag-openai' 'mkraglab'         # nombres de recursos
  '/Users/'                          # rutas personales
  '\.agentmax'                       # el harness privado
  'tailscale' 'tailnet'              # topología de red
  '100\.[0-9]+\.[0-9]+\.[0-9]+'      # IPs de tailnet
  'ssh ' 'scp '                      # accesos a otras máquinas
  '(^|[^A-Za-z])eyJ[A-Za-z0-9_-]{10,}'  # JWT
  '\b[0-9a-f]{32,}\b'                # claves hex
  'BEGIN [A-Z ]*PRIVATE KEY'
  'subscriptionId|tenantId'
)

fail=0
echo "== árbol de trabajo"
for pat in "${PATTERNS[@]}"; do
  hits=$(git grep -n -I -E "$pat" -- . 2>/dev/null | grep -v -e '^uv.lock' -e 'scripts/scan_public.sh' || true)
  if [ -n "$hits" ]; then
    echo "  ✗ /$pat/"
    echo "$hits" | head -3 | sed 's/^/      /'
    fail=1
  fi
done

echo "== historial completo"
for pat in "${PATTERNS[@]}"; do
  hits=$(git log --all -p -- . ':!scripts/scan_public.sh' ':!uv.lock' 2>/dev/null \
    | grep -v '^+++' | grep -E "^\+" | grep -E "$pat" | grep -v 'pythonhosted' | head -2 || true)
  if [ -n "$hits" ]; then
    echo "  ✗ historial /$pat/"
    echo "$hits" | sed 's/^/      /' | cut -c1-140
    fail=1
  fi
done

if [ "$fail" -eq 0 ]; then
  echo "OK — nada que ocultar en el árbol ni en el historial"
else
  echo
  echo "FALLA: limpiá el árbol y, si el hallazgo está en el historial, reescribilo"
  echo "       (un archivo corregido no borra un commit viejo)."
fi
exit "$fail"
