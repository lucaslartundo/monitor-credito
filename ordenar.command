#!/bin/bash
# ============================================================================
#  Ordenar carpeta del monitor — para Mac
#
#  Deja la carpeta con la estructura correcta:
#    - verifica que estén todos los archivos que deben estar
#    - avisa cuáles faltan
#    - borra basura y versiones viejas (index.v1.html, .pyc, __pycache__, etc.)
#    - crea las subcarpetas que falten
#    - protege claves.env y te dice si está bien configurado
#
#  No borra nada importante. Antes de borrar cualquier cosa dudosa, pregunta.
# ============================================================================
set -e
V='\033[0;32m'; A='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'; N='\033[0m'; B='\033[1m'
ok(){   echo -e "${V}✓${N} $1"; }
falta(){ echo -e "${R}✗ falta:${N} $1"; }
info(){ echo -e "${A}▸${N} $1"; }
titulo(){ echo -e "\n${B}$1${N}"; }

cd "$(dirname "$0")"
clear
echo -e "${B}  Ordenar carpeta del monitor${N}"
echo -e "  Carpeta: $(pwd)\n"

# ----------------------------------------------------------------------------
titulo "1 · Creando subcarpetas necesarias"
# ----------------------------------------------------------------------------
for d in collector data assets .github/workflows; do
  if [ -d "$d" ]; then ok "$d"; else mkdir -p "$d"; info "creada $d"; fi
done

# ----------------------------------------------------------------------------
titulo "2 · Verificando archivos del proyecto"
# ----------------------------------------------------------------------------
ESENCIALES=(
  "index.html"
  "actualizar.command"
  "collector/run.py"
  "collector/ia.py"
  "collector/fuentes.py"
  "collector/requirements.txt"
  "data/alias_emisores.json"
  ".gitignore"
)
FALTANTES=0
for f in "${ESENCIALES[@]}"; do
  if [ -f "$f" ]; then ok "$f"; else falta "$f"; FALTANTES=$((FALTANTES+1)); fi
done

# ----------------------------------------------------------------------------
titulo "3 · Limpiando basura y versiones viejas"
# ----------------------------------------------------------------------------
# Patrones seguros de borrar: caché de Python, basura de Mac, backups, versiones.
BORRADOS=0
limpiar(){
  # $1 = patrón find
  while IFS= read -r item; do
    [ -z "$item" ] && continue
    rm -rf "$item"
    echo -e "  ${C}borrado${N} ${item#./}"
    BORRADOS=$((BORRADOS+1))
  done < <(eval "$1" 2>/dev/null)
}
limpiar "find . -name '__pycache__' -type d -not -path './.git/*'"
limpiar "find . -name '*.pyc' -not -path './.git/*'"
limpiar "find . -name '.DS_Store' -not -path './.git/*'"
limpiar "find . -name 'index.v*.html' -not -path './.git/*'"
limpiar "find . -name '*.backup' -o -name '*.bak' -o -name '*~' 2>/dev/null | grep -v '/.git/'"
# agencies/ vacía o parse.py viejo (del enfoque sin IA) — preguntar antes
if [ -f "collector/parse.py" ]; then
  echo ""
  info "Encontré 'collector/parse.py' (del recolector viejo sin IA)."
  read -p "  ¿Borrarlo? Ya no se usa con Firecrawl [s/N]: " R1
  if [[ "$R1" =~ ^[sS]$ ]]; then rm -f collector/parse.py collector/agencies.py collector/test_emisor.py; echo -e "  ${C}borrados${N} parse.py, agencies.py, test_emisor.py"; fi
fi
[ "$BORRADOS" -eq 0 ] && ok "No había basura que limpiar"

# ----------------------------------------------------------------------------
titulo "4 · Revisando las claves de API"
# ----------------------------------------------------------------------------
if [ -f "claves.env" ]; then
  if grep -q "FIRECRAWL_API_KEY=fc-" claves.env 2>/dev/null; then
    ok "claves.env configurado (Firecrawl detectada)"
  else
    info "claves.env existe pero revisa que tenga: FIRECRAWL_API_KEY=fc-..."
  fi
else
  info "No hay claves.env todavía. Créalo con:"
  echo "     FIRECRAWL_API_KEY=fc-tu-clave"
fi

# Asegurar que .gitignore protege las claves
if [ -f ".gitignore" ] && ! grep -q "claves.env" .gitignore; then
  echo "claves.env" >> .gitignore
  info "Agregué claves.env al .gitignore (protección)"
fi

# ----------------------------------------------------------------------------
titulo "5 · Permisos de los .command"
# ----------------------------------------------------------------------------
for c in *.command; do
  [ -f "$c" ] || continue
  chmod +x "$c"
  ok "$c ejecutable"
done

# ----------------------------------------------------------------------------
titulo "Resumen"
# ----------------------------------------------------------------------------
echo -e "  Archivos borrados: ${C}$BORRADOS${N}"
if [ "$FALTANTES" -eq 0 ]; then
  echo -e "  ${V}${B}Carpeta ordenada y completa.${N}"
  echo ""
  echo "  Siguiente paso: doble clic en actualizar.command"
else
  echo -e "  ${R}Faltan $FALTANTES archivo(s)${N} — descárgalos y vuelve a correr esto."
fi
echo ""
echo -e "${B}Estructura actual:${N}"
# arbol simple sin depender de 'tree'
find . -not -path './.git/*' -not -path './.venv/*' -not -name '.DS_Store' \
  | sed -e 's|[^/]*/|  |g' -e 's|^  ||' | sort | head -40
echo ""
read -p "  ENTER para cerrar… "
