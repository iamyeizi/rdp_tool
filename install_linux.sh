#!/usr/bin/env bash
set -euo pipefail

# install_linux.sh - Configura venv o sistema, instala deps, crea lanzador .desktop
# Uso: ./install_linux.sh [--system | --mode=system] [--build]

# 0) Parseo simple de argumentos
# Modo por defecto: preguntar si no se especifica (venv recomendado)
MODE="${IT_MODE:-}"
[[ -n "$MODE" ]] || MODE=""  # vacío => preguntar
BUILD=false
for arg in "$@"; do
  case "$arg" in
    --use-system-python|--system)
      MODE="system";
      ;;
    --mode=*)
      MODE="${arg#*=}";
      ;;
    --build)
      BUILD=true;
      ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"
LOG_FILE="$ROOT_DIR/install_linux.log"

# Selección de Python
PY_CANDIDATES=()
[[ -n "${IT_PYTHON:-}" ]] && PY_CANDIDATES+=("$IT_PYTHON")
[[ -n "${PYTHON:-}" ]] && PY_CANDIDATES+=("$PYTHON")
PY_CANDIDATES+=(python3 python3.12 python3.11 python3.10 python3.9 python3.8)
PY=""
for cand in "${PY_CANDIDATES[@]}"; do
  if command -v "$cand" >/dev/null 2>&1; then
    PY="$cand"; break
  fi
done

# Logging a archivo y consola
rm -f "$LOG_FILE" 2>/dev/null || true
exec > >(tee -a "$LOG_FILE") 2>&1

log(){ echo -e "[install] $*"; }

# Detección básica de distro
DISTRO_ID=""
DISTRO_LIKE=""
if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  DISTRO_ID="${ID:-}"
  DISTRO_LIKE="${ID_LIKE:-}"
fi
if [[ -n "$DISTRO_ID" ]]; then
  log "Distro detectada: ID=${DISTRO_ID} ID_LIKE=${DISTRO_LIKE}"
fi

# 0.1) Elegir modo si no vino por flag/env
if [[ -z "$MODE" ]]; then
  echo
  echo "Cómo querés instalar iTool?"
  echo "  1) venv (recomendado) - crea un entorno virtual aislado en $VENV_DIR"
  echo "  2) system          - usa python del sistema e instala dependencias en el user-site"
  echo
  if [[ -t 0 ]]; then
    read -r -p "Elegí opción [1/2] (por defecto 1): " _opt
  else
    _opt=1
  fi
  case "${_opt:-1}" in
    2) MODE="system" ;;
    *) MODE="venv" ;;
  esac
fi
log "Modo seleccionado: ${MODE}"

if [[ -z "$PY" ]]; then
  echo "No se encontró un intérprete Python 3.8+ (probé: ${PY_CANDIDATES[*]})." >&2
  echo "Instalá Python 3 (p. ej. 3.12) con tu gestor de paquetes y reintentá." >&2
  exit 1
fi

# 1.0) Verificar versión mínima (3.8+)
read -r PY_MAJOR PY_MINOR < <($PY -c 'import sys; print(sys.version_info.major, sys.version_info.minor)')
if (( PY_MAJOR < 3 || (PY_MAJOR == 3 && PY_MINOR < 8) )); then
  echo "Se requiere Python 3.8 o superior. Detectado: $($PY --version 2>&1)." >&2
  exit 1
fi

if [[ "$MODE" == "venv" ]]; then

  # 1.1) Verificar ensurepip/venv disponible; en Debian/Ubuntu se requiere el paquete pythonX.Y-venv
PY_MAJMIN="$($PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
USE_VIRTUALENV=false
if ! "$PY" -m ensurepip --version >/dev/null 2>&1; then
  log "El módulo 'ensurepip' no está disponible para Python ${PY_MAJMIN}."
  if command -v apt >/dev/null 2>&1 || command -v apt-get >/dev/null 2>&1 || [[ "$DISTRO_LIKE" =~ debian|ubuntu || "$DISTRO_ID" =~ debian|ubuntu ]]; then
    echo "Sugerencia (Debian/Ubuntu): sudo apt install python${PY_MAJMIN}-venv" >&2
    read -r -p "¿Intentar instalarlo ahora con sudo? [S/n] " _ans
    _ans=${_ans:-S}
    if [[ "${_ans^^}" == "S" ]]; then
      if command -v apt >/dev/null 2>&1; then
        sudo apt update && sudo apt install -y "python${PY_MAJMIN}-venv"
      else
        sudo apt-get update && sudo apt-get install -y "python${PY_MAJMIN}-venv"
      fi
    fi
  elif command -v dnf >/dev/null 2>&1 || [[ "$DISTRO_LIKE" =~ fedora|rhel|centos || "$DISTRO_ID" =~ fedora|rhel|centos ]]; then
    echo "Sugerencia (Fedora/RHEL/CentOS): instalar virtualenv o el paquete de pip: sudo dnf install python3-virtualenv python${PY_MAJMIN}-pip" >&2
    read -r -p "¿Intentar instalar 'python3-virtualenv' ahora con sudo? [S/n] " _ans
    _ans=${_ans:-S}
    if [[ "${_ans^^}" == "S" ]]; then
      sudo dnf install -y python3-virtualenv python${PY_MAJMIN}-pip || true
    fi
    USE_VIRTUALENV=true
  elif command -v pacman >/dev/null 2>&1 || [[ "$DISTRO_LIKE" =~ arch || "$DISTRO_ID" =~ arch ]]; then
    echo "Sugerencia (Arch/Manjaro): sudo pacman -S python python-pip python-virtualenv" >&2
    read -r -p "¿Intentar instalar 'python-virtualenv' ahora con sudo? [S/n] " _ans
    _ans=${_ans:-S}
    if [[ "${_ans^^}" == "S" ]]; then
      sudo pacman -S --noconfirm python python-pip python-virtualenv || true
    fi
    USE_VIRTUALENV=true
  else
    echo "Instala el paquete de 'venv' para tu distribución (python${PY_MAJMIN}-venv o equivalente), o bien 'virtualenv'." >&2
    # Como alternativa genérica, intentaremos usar virtualenv si existe
    USE_VIRTUALENV=true
  fi
  # Re-verificar luego de la instalación opcional
  if ! "$PY" -m ensurepip --version >/dev/null 2>&1; then
    if [[ "$USE_VIRTUALENV" == true ]]; then
      if ! command -v virtualenv >/dev/null 2>&1; then
        # Intentar instalar virtualenv vía pip del sistema si existe
        if command -v pip3 >/dev/null 2>&1; then
          log "Instalando virtualenv con pip de usuario..."
          pip3 install --user virtualenv || true
        fi
      fi
      if ! command -v virtualenv >/dev/null 2>&1; then
        echo "No se pudo disponer de ensurepip ni de virtualenv. Por favor instala python${PY_MAJMIN}-venv o virtualenv y reintentá." >&2
        exit 1
      fi
      log "Se utilizará virtualenv como alternativa a venv."
    else
      echo "ensurepip aún no está disponible. Volvé a ejecutar este script después de instalar venv." >&2
      exit 1
    fi
  fi
fi

  # 2) Crear venv (y recrear si está corrupto o incompleto)
need_create=true
if [[ -d "$VENV_DIR" ]]; then
  if [[ -x "$VENV_DIR/bin/python" ]]; then
    need_create=false
  else
    log "Se detectó un venv incompleto en $VENV_DIR; se recreará."
    rm -rf "$VENV_DIR"
  fi
fi

if [[ "$need_create" == true ]]; then
  log "Creando entorno virtual..."
  if [[ "$USE_VIRTUALENV" == true ]]; then
    virtualenv -p "$PY" "$VENV_DIR"
  else
    "$PY" -m venv "$VENV_DIR"
  fi
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

else
  # Modo system: instalar dependencias en user-site
  PIP_CMD=("$PY" -m pip)
  if ! "$PY" -m pip --version >/dev/null 2>&1; then
    if command -v pip3 >/dev/null 2>&1; then
      PIP_CMD=(pip3)
    fi
  fi
  if ! "${PIP_CMD[@]}" --version >/dev/null 2>&1; then
    if command -v apt >/dev/null 2>&1 || command -v apt-get >/dev/null 2>&1 || [[ "$DISTRO_LIKE" =~ debian|ubuntu || "$DISTRO_ID" =~ debian|ubuntu ]]; then
      log "Instalando python3-pip con apt..."
      if command -v apt >/dev/null 2>&1; then
        sudo apt update && sudo apt install -y python3-pip
      else
        sudo apt-get update && sudo apt-get install -y python3-pip
      fi
      PIP_CMD=(pip3)
    elif command -v dnf >/dev/null 2>&1 || [[ "$DISTRO_LIKE" =~ fedora|rhel|centos || "$DISTRO_ID" =~ fedora|rhel|centos ]]; then
      log "Instalando python3-pip con dnf..."
      sudo dnf install -y python3-pip
      PIP_CMD=(pip3)
    elif command -v pacman >/dev/null 2>&1 || [[ "$DISTRO_LIKE" =~ arch || "$DISTRO_ID" =~ arch ]]; then
      log "Instalando python-pip con pacman..."
      sudo pacman -S --noconfirm python-pip
      PIP_CMD=(pip3)
    fi
  fi
  if ! "${PIP_CMD[@]}" --version >/dev/null 2>&1; then
    echo "No se pudo disponer de pip. Instalá pip para Python y reintentá o usá el modo venv (por defecto)." >&2
    exit 1
  fi
  # Preparar flags pip para entorno administrado (PEP 668)
  PIP_FLAGS=(--user)
  if [[ "$DISTRO_ID" =~ (debian|ubuntu) || "$DISTRO_LIKE" =~ (debian|ubuntu) ]]; then
    PIP_FLAGS+=(--break-system-packages)
  fi
  log "Actualizando pip..."
  "${PIP_CMD[@]}" install "${PIP_FLAGS[@]}" --upgrade pip setuptools wheel || true
  if [[ -f "$ROOT_DIR/requirements.txt" ]]; then
    log "Instalando requirements en user-site..."
    "${PIP_CMD[@]}" install "${PIP_FLAGS[@]}" -r "$ROOT_DIR/requirements.txt"
  fi
fi

# 4) Crear .desktop en el usuario
APP_NAME="iTool"
DESKTOP_FILE="$HOME/.local/share/applications/itool.desktop"
ICON_PNG="$ROOT_DIR/utils/icon.png"

if [[ ! -f "$ICON_PNG" ]]; then
  log "Advertencia: no existe utils/icon.png, el lanzador usará un ícono genérico."
fi

if [[ "$MODE" == "venv" ]]; then
  EXEC_CMD="\"$PYVENV\" \"$ROOT_DIR/main.py\""
else
  EXEC_CMD="\"$PY\" \"$ROOT_DIR/main.py\""
fi

log "Creando archivo .desktop en $DESKTOP_FILE"
mkdir -p "$(dirname "$DESKTOP_FILE")"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_NAME
Comment=Herramienta iTool
Exec=$EXEC_CMD
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
if [[ "$BUILD" == true ]]; then
  log "Instalando PyInstaller y empaquetando..."
  if [[ "$MODE" == "venv" ]]; then
    "$PIP" install pyinstaller
    PYI_BIN="$VENV_DIR/bin/pyinstaller"
  else
    # intentar pyinstaller con pip de usuario
    if ! command -v pyinstaller >/dev/null 2>&1; then
      "${PIP_CMD[@]}" install --user pyinstaller
    fi
    PYI_BIN="$(command -v pyinstaller)"
  fi
  ADD_DATA=(
    "credential.json:."
    "utils/template.rdp:utils"
    "utils/icon.ico:utils"
    "utils/icon.png:utils"
  )
  ADD_ARGS=()
  for x in "${ADD_DATA[@]}"; do
    ADD_ARGS+=( --add-data "$x" )
  done
  ICON_ARG=()
  if [[ -f "$ROOT_DIR/utils/icon.ico" ]]; then
    ICON_ARG=( --icon "$ROOT_DIR/utils/icon.ico" )
  fi
  "$PYI_BIN" --noconfirm --onefile --windowed --name itool "${ICON_ARG[@]}" "${ADD_ARGS[@]}" "$ROOT_DIR/main.py"
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
