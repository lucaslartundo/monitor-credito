#!/bin/bash
# ============================================================================
#  Actualizar datos del monitor (con IA) — corre en tu Mac
#
#  Usa Firecrawl (entra a los sitios) + Anthropic (extrae y resume).
#  Necesita dos claves, que defines UNA VEZ en el archivo  claves.env
#  (ver LEEME). Nunca van al repositorio.
# ============================================================================
set -e
V='\033[0;32m'; A='\033[1;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
ok(){ echo -e "${V}✓${N} $1"; }; info(){ echo -e "${A}▸${N} $1"; }
paso(){ echo -e "\n${B}$1${N}"; }

cd "$(dirname "$0")"
clear
echo -e "${B}  Actualizar monitor de clasificaciones (IA)${N}\n"

# --- Claves ---
paso "Paso 1 · Claves de API"
if [ -f claves.env ]; then
  set -a; source claves.env; set +a
  ok "Claves cargadas desde claves.env"
else
  echo -e "${R}No encontré el archivo claves.env${N}"
  echo "  Créalo en esta carpeta con este contenido (tus claves reales):"
  echo ""
  echo "    FIRECRAWL_API_KEY=fc-tu-clave-aqui"
  echo "    ANTHROPIC_API_KEY=sk-ant-tu-clave-aqui"
  echo ""
  echo "  Cómo obtenerlas: ver LEEME.md, sección 'Claves de API'."
  read -p "  ENTER para cerrar… "; exit 1
fi
if [ -z "$FIRECRAWL_API_KEY" ]; then
  echo -e "${R}Falta FIRECRAWL_API_KEY en claves.env${N}"; read -p "  ENTER… "; exit 1
fi

# --- Entorno ---
paso "Paso 2 · Entorno de Python"
if [ ! -d ".venv" ]; then
  info "Primera vez: creando entorno…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r collector/requirements.txt
fi
ok "Entorno listo"

# --- Recolectar ---
paso "Paso 3 · Recolectando con IA"
RANGO="${1:-}"
info "Consultando las 4 clasificadoras…"
./.venv/bin/python collector/run.py $RANGO --con-resumen || {
  echo -e "${R}Falló. Copia lo de arriba y mándalo.${N}"; read -p "  ENTER… "; exit 1; }
ok "Datos recolectados"

# --- Subir ---
paso "Paso 4 · Subiendo a GitHub"
if git diff --quiet data/ 2>/dev/null && git diff --staged --quiet data/ 2>/dev/null; then
  info "Sin cambios nuevos."
else
  git add data/
  git commit -q -m "datos: $(date +%Y-%m-%d\ %H:%M)"
  git push -q 2>/dev/null && ok "Subido. La página se actualiza en 1-2 min." || git push
fi

USUARIO="$(git remote get-url origin 2>/dev/null | sed -E 's#.*github.com[:/]([^/]+)/.*#\1#')"
REPO="$(git remote get-url origin 2>/dev/null | sed -E 's#.*/([^/]+)\.git#\1#')"
echo ""
[ -n "$USUARIO" ] && echo -e "  Página: ${B}https://$USUARIO.github.io/$REPO${N}"
echo ""
read -p "  ENTER para cerrar… "
