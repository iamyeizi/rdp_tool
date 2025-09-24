#!/usr/bin/env bash
set -euo pipefail

# install_linux.sh - Configura venv, instala deps, crea lanzador .desktop
# Uso: ./install_linux.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"
PY="python3"
LOG_FILE="$ROOT_DIR/install_linux.log"

# Logging a archivo y consola
rm -f "$LOG_FILE" 2>/dev/null || true
exec > >(tee -a "$LOG_FILE") 2>&1

log(){ echo -e "[install] $*"; }

# 1) Verificar Python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python3 no encontrado. Instalalo desde tu distro (apt/dnf/pacman)." >&2
  exit 1
fi

# 2) Crear venv
if [[ ! -d "$VENV_DIR" ]]; then
  log "Creando entorno virtual..."
  "$PY" -m venv "$VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
PYVENV="$VENV_DIR/bin/python"

# 3) Actualizar pip y deps
log "Actualizando pip..."
"$PIP" install --upgrade pip setuptools wheel

if [[ -f "$ROOT_DIR/requirements.txt" ]]; then
  log "Instalando requirements..."
  "$PIP" install -r "$ROOT_DIR/requirements.txt"
fi

# 4) Crear .desktop en el usuario
APP_NAME="iTool"
DESKTOP_FILE="$HOME/.local/share/applications/itool.desktop"
ICON_PNG="$ROOT_DIR/utils/app.png"

if [[ ! -f "$ICON_PNG" ]]; then
  log "Advertencia: no existe utils/app.png, el lanzador usará un ícono genérico."
fi

log "Creando archivo .desktop en $DESKTOP_FILE"
mkdir -p "$(dirname "$DESKTOP_FILE")"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_NAME
Comment=Herramienta iTool
Exec=$PYVENV "$ROOT_DIR/main.py"
Icon=${ICON_PNG}
Terminal=false
Categories=Utility;
EOF

# 5) Actualizar base de datos de desktop
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$HOME/.local/share/applications" || true
fi

log "Listo. Buscá 'iTool' en tu launcher/menú y fijalo si querés."

# 6) Opción: empaquetar con PyInstaller si se llama con --build
if [[ "${1:-}" == "--build" ]]; then
  log "Instalando PyInstaller y empaquetando..."
  "$PIP" install pyinstaller
  ADD_DATA=(
    "credential.json:."
    "utils/template.rdp:utils"
    "utils/app.ico:utils"
    "utils/app.png:utils"
  )
  ADD_ARGS=()
  for x in "${ADD_DATA[@]}"; do
    ADD_ARGS+=( --add-data "$x" )
  done
  ICON_ARG=()
  if [[ -f "$ROOT_DIR/utils/app.ico" ]]; then
    ICON_ARG=( --icon "$ROOT_DIR/utils/app.ico" )
  fi
  "$VENV_DIR/bin/pyinstaller" --noconfirm --onefile --windowed --name itool "${ICON_ARG[@]}" "${ADD_ARGS[@]}" "$ROOT_DIR/main.py"
  BIN_PATH="$ROOT_DIR/dist/itool"
  if [[ -f "$BIN_PATH" ]]; then
    log "Actualizando .desktop para usar el binario empaquetado..."
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_NAME
Comment=Herramienta iTool
Exec=$BIN_PATH
Icon=${ICON_PNG}
Terminal=false
Categories=Utility;
EOF
  else
    log "No se encontró $BIN_PATH; el .desktop seguirá apuntando a main.py en venv."
  fi
  log "Binario Linux disponible en dist/itool y .desktop actualizado si corresponde"
fi
