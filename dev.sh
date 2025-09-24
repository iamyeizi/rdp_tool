#!/usr/bin/env bash
set -euo pipefail

# dev.sh - Script de desarrollo para iTool (equivalente a dev.ps1)
# Uso:
#   chmod +x dev.sh
#   ./dev.sh

# --- Helpers ---
log() { printf "%b\n" "$*"; }
info() { log "[INFO] $*"; }
ok()   { log "[OK]   $*"; }
warn() { log "[WARN] $*"; }
err()  { log "[ERR]  $*" >&2; }

# Ir al directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

printf "\n\033[33m🔴 Iniciando iTool (dev) ...\033[0m\n\n"

# Verificar archivos clave
if [[ ! -f "main.py" ]]; then
  err "No se encontró main.py en $SCRIPT_DIR"
  exit 1
fi

# Crear directorio de logs si no existe
mkdir -p logs

# Verificar Python
if ! command -v python3 >/dev/null 2>&1; then
  err "Python3 no encontrado. Instalalo con el gestor de paquetes de tu distro."
  exit 1
fi
ok "Python: $(python3 -V)"

# Verificar requirements
if [[ ! -f "requirements.txt" ]]; then
  err "requirements.txt no encontrado"
  exit 1
fi

# Verificar credenciales
if [[ ! -f "credential.json" ]]; then
  if [[ -f "credential.example.json" ]]; then
    warn "No se encontró credential.json, usando credential.example.json como referencia (copiá y completá)."
  else
    err "Falta credential.json (Google Service Account)."
    exit 1
  fi
fi

# Aviso sobre template.rdp (usado en Windows)
if [[ ! -f "utils/template.rdp" ]]; then
  warn "Falta utils/template.rdp (sólo afecta RDP en Windows)."
fi

# Asegurar pip presente
if ! python3 -m pip -V >/dev/null 2>&1; then
  err "pip no está disponible en python3. Instalalo (p. ej. sudo apt install python3-pip)."
  exit 1
fi

# Verificar/instalar pipenv
if ! command -v pipenv >/dev/null 2>&1; then
  info "pipenv no encontrado. Instalando en --user..."
  python3 -m pip install --user pipenv || {
    err "No se pudo instalar pipenv."
    exit 1
  }
  # Asegurar ~/.local/bin en PATH para esta sesión
  export PATH="$HOME/.local/bin:$PATH"
fi
ok "Pipenv: $(pipenv --version 2>/dev/null || echo "instalado")"

# Instalar dependencias en entorno de pipenv usando requirements.txt
info "Instalando dependencias desde requirements.txt..."
pipenv install -r requirements.txt
ok "Dependencias listas."

# Ejecutar la app
printf "\n\033[33mPresione Ctrl+C para detener la app\033[0m\n\n"
pipenv run python3 main.py

printf "\n\033[33mApp detenida.\033[0m\n"
