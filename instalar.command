#!/bin/bash
# ============================================================================
#  Instalador del Monitor de Clasificaciones — para Mac
#
#  Que hace:
#    1. Revisa que tengas las herramientas (git, python)
#    2. Prepara la carpeta con los archivos correctos
#    3. Te ayuda a conectarte a GitHub (una sola vez)
#    4. Crea el repositorio y sube todo
#
#  Lo unico que NO hace por ti: crear tu cuenta y poner tu contrasena.
#  Eso lo haces tu en el navegador, por seguridad.
# ============================================================================

set -e  # si algo falla, para y avisa

# Colores para que se lea facil
V='\033[0;32m'; A='\033[1;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
ok(){ echo -e "${V}✓${N} $1"; }
info(){ echo -e "${A}▸${N} $1"; }
error(){ echo -e "${R}✗ $1${N}"; }
titulo(){ echo -e "\n${B}$1${N}"; }

clear
echo -e "${B}"
echo "  ┌─────────────────────────────────────────────┐"
echo "  │   Monitor de Clasificaciones de Riesgo      │"
echo "  │   Instalador para GitHub · Mac              │"
echo "  └─────────────────────────────────────────────┘"
echo -e "${N}"
echo "  Este asistente sube el proyecto a tu GitHub."
echo "  Te va a ir explicando cada paso. No te apures."
echo ""
read -p "  Presiona ENTER para empezar… "

# ----------------------------------------------------------------------------
titulo "Paso 1 de 6 · Revisando tu Mac"
# ----------------------------------------------------------------------------

# --- git ---
if command -v git &>/dev/null; then
  ok "git instalado"
else
  info "Falta git. Se abrira una ventana de Apple para instalarlo."
  info "Dale 'Instalar', espera a que termine, y vuelve a correr este script."
  xcode-select --install 2>/dev/null || true
  exit 0
fi

# --- python ---
PY=""
if command -v python3 &>/dev/null; then
  PY="python3"; ok "python3 instalado ($(python3 --version 2>&1))"
else
  error "Falta Python."
  echo "  Instalalo desde: https://www.python.org/downloads/"
  echo "  Descarga el instalador para macOS, abrelo, y vuelve a correr este script."
  exit 1
fi

# ----------------------------------------------------------------------------
titulo "Paso 2 de 6 · Preparando la carpeta del proyecto"
# ----------------------------------------------------------------------------

# El script se corre desde la carpeta que contiene los archivos del proyecto.
CARPETA="$(cd "$(dirname "$0")" && pwd)"
cd "$CARPETA"
ok "Trabajando en: $CARPETA"

# Verificar que estan los archivos que deben estar
FALTAN=""
for f in index.html collector/run.py collector/parse.py collector/agencies.py \
         collector/requirements.txt .github/workflows/recolectar.yml; do
  [ -f "$f" ] || FALTAN="$FALTAN\n     $f"
done
if [ -n "$FALTAN" ]; then
  error "Faltan archivos en esta carpeta:"
  echo -e "$FALTAN"
  echo ""
  echo "  Asegurate de correr este script DENTRO de la carpeta 'monitor',"
  echo "  con todos los archivos que descargaste ya adentro."
  exit 1
fi
ok "Todos los archivos del proyecto estan presentes"

# Los datos que genera el robot no se suben; se ignoran.
cat > .gitignore <<'EOF'
# Datos que genera el recolector — los crea GitHub Actions, no se suben a mano
data/clasificaciones.json
data/historial.json
# Basura de Mac y Python
.DS_Store
__pycache__/
*.pyc
EOF
ok "Configurado que los datos generados no se suban"

# ----------------------------------------------------------------------------
titulo "Paso 3 de 6 · Conectando con GitHub"
# ----------------------------------------------------------------------------

# gh es la herramienta oficial de GitHub. Simplifica el login enormemente.
if ! command -v gh &>/dev/null; then
  info "Falta la herramienta oficial de GitHub ('gh'). Vamos a instalarla."
  if command -v brew &>/dev/null; then
    info "Instalando con Homebrew… (puede tardar un par de minutos)"
    brew install gh
  else
    error "Necesitas Homebrew o instalar 'gh' a mano."
    echo ""
    echo "  Opcion facil — pega esto en la Terminal y sigue las instrucciones:"
    echo -e "  ${B}/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"${N}"
    echo ""
    echo "  Cuando termine, instala gh con:  ${B}brew install gh${N}"
    echo "  y vuelve a correr este script."
    exit 1
  fi
fi
ok "Herramienta de GitHub lista"

# Login: gh abre el navegador para que te autentiques de forma segura.
# Tu contrasena nunca pasa por este script.
if gh auth status &>/dev/null; then
  ok "Ya estas conectado a GitHub como: $(gh api user --jq .login 2>/dev/null)"
else
  echo ""
  info "Ahora vas a conectarte a tu cuenta de GitHub."
  info "Se abrira tu navegador. Ahi apruebas la conexion."
  info "Si aun no tienes cuenta, creala primero en github.com y vuelve aca."
  echo ""
  read -p "  Presiona ENTER para abrir el navegador… "
  # Login por navegador, protocolo https (mas simple que SSH para principiantes)
  gh auth login --hostname github.com --git-protocol https --web
  ok "Conectado a GitHub"
fi

USUARIO="$(gh api user --jq .login)"

# ----------------------------------------------------------------------------
titulo "Paso 4 de 6 · Creando el repositorio"
# ----------------------------------------------------------------------------

NOMBRE_REPO="monitor-clasificaciones"
echo "  Se creara un repositorio PUBLICO llamado: ${B}$NOMBRE_REPO${N}"
echo "  (publico es necesario para que GitHub Pages sea gratis)"
echo ""
read -p "  ¿Usar ese nombre? ENTER para si, o escribe otro nombre: " OTRO
[ -n "$OTRO" ] && NOMBRE_REPO="$OTRO"

# Arrancar git en la carpeta si no estaba
if [ ! -d .git ]; then
  git init -q
  git branch -M main
fi
git add -A
git -c user.email="$USUARIO@users.noreply.github.com" \
    -c user.name="$USUARIO" commit -q -m "Versión inicial del monitor" || true
ok "Cambios preparados"

# Crear el repo en GitHub y subir en un solo paso
if gh repo view "$USUARIO/$NOMBRE_REPO" &>/dev/null; then
  info "Ese repo ya existe. Subiendo los archivos a el…"
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$USUARIO/$NOMBRE_REPO.git"
  git push -u origin main
else
  info "Creando el repositorio y subiendo todo…"
  gh repo create "$NOMBRE_REPO" --public --source=. --remote=origin --push
fi
ok "Repositorio creado y archivos subidos"

# ----------------------------------------------------------------------------
titulo "Paso 5 de 6 · Dando permisos al robot"
# ----------------------------------------------------------------------------

# El workflow necesita permiso de escritura para guardar los datos.
info "Habilitando que Actions pueda guardar los datos…"
gh api -X PUT "repos/$USUARIO/$NOMBRE_REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=write &>/dev/null \
  && ok "Permisos del robot configurados" \
  || info "No pude configurarlo automaticamente — hay que hacerlo a mano (te digo abajo)"

# ----------------------------------------------------------------------------
titulo "Paso 6 de 6 · Encendiendo la pagina web"
# ----------------------------------------------------------------------------

info "Activando GitHub Pages…"
gh api -X POST "repos/$USUARIO/$NOMBRE_REPO/pages" \
  -f "source[branch]=main" -f "source[path]=/" &>/dev/null \
  && ok "GitHub Pages activado" \
  || info "Actívalo a mano en Settings → Pages (te digo abajo)"

# ----------------------------------------------------------------------------
echo -e "\n${B}════════════════════════════════════════════════${N}"
echo -e "${V}${B}  ¡Listo! El proyecto está en GitHub.${N}"
echo -e "${B}════════════════════════════════════════════════${N}\n"

echo "  Tu repositorio:"
echo -e "  ${B}https://github.com/$USUARIO/$NOMBRE_REPO${N}\n"

echo "  Tu página (tarda 2-3 minutos en aparecer la primera vez):"
echo -e "  ${B}https://$USUARIO.github.io/$NOMBRE_REPO${N}\n"

echo -e "${A}  Falta un paso que tienes que hacer tú, en el navegador:${N}"
echo ""
echo "  Correr el recolector por primera vez para que baje los datos:"
echo "    1. Entra a tu repo (link de arriba)"
echo "    2. Pestaña 'Actions'"
echo "    3. Si pide habilitar workflows, acepta"
echo "    4. Elige 'Recolectar clasificaciones' → 'Run workflow'"
echo "    5. Escribe 180 en días → botón verde 'Run workflow'"
echo ""
echo "  En unos minutos el círculo se pone verde y la página muestra datos."
echo ""
echo -e "  Si algo salió en amarillo arriba, entra a ${B}Settings${N} del repo:"
echo "    • Actions → General → 'Read and write permissions' → Save"
echo "    • Pages → Source: 'main' / '(root)' → Save"
echo ""
read -p "  Presiona ENTER para abrir tu repo en el navegador… "
open "https://github.com/$USUARIO/$NOMBRE_REPO/actions"
