#!/usr/bin/env pwsh

Write-Host ""
Write-Host "🔴 Iniciando RDP Tool..." -ForegroundColor Yellow
Write-Host ""

# Detectar si estamos en el directorio raíz y navegar a la carpeta correcta
$currentLocation = Get-Location
if ((Split-Path -Leaf $currentLocation) -ne "rdp_tool") {
    if (Test-Path "rdp_tool") {
        Write-Host "📁 Navegando a rdp_tool..." -ForegroundColor Cyan
        Set-Location "rdp_tool"
    } else {
        Write-Host "❌ ERROR: No se puede encontrar la carpeta rdp_tool" -ForegroundColor Red
        Write-Host "Asegúrese de ejecutar este script desde:" -ForegroundColor Yellow
        Write-Host "  - La carpeta rdp_tool, o" -ForegroundColor Yellow
        Write-Host "  - El directorio raíz del proyecto" -ForegroundColor Yellow
        Read-Host "Presione Enter para salir"
        exit 1
    }
}

# Verificar si Python está instalado
try {
    $pythonVersion = python -V 2>&1
    Write-Host "✅ Python encontrado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ ERROR: Python no encontrado. Instale Python desde https://python.org" -ForegroundColor Red
    Read-Host "Presione Enter para salir"
    exit 1
}

# Verificar si pipenv está instalado
try {
    $pipenvVersion = pipenv --version 2>&1
    Write-Host "✅ Pipenv encontrado: $pipenvVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ ERROR: Pipenv no encontrado. Instalando..." -ForegroundColor Yellow
    pip install pipenv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Error instalando pipenv" -ForegroundColor Red
        Read-Host "Presione Enter para salir"
        exit 1
    }
}

# Crear directorio de logs si no existe
if (-not (Test-Path "logs")) {
    Write-Host "📁 Creando directorio de logs..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

# Verificar si requirements.txt existe
if (-not (Test-Path "requirements.txt")) {
    Write-Host "❌ ERROR: requirements.txt no encontrado" -ForegroundColor Red
    Read-Host "Presione Enter para salir"
    exit 1
}

# Obtener el directorio home del usuario actual
$userHome = [Environment]::GetFolderPath("UserProfile")
$virtualenvsPath = Join-Path $userHome ".virtualenvs"

# Obtener el hash del proyecto actual para identificar el venv
$projectPath = (Get-Location).Path
$projectName = (Get-Item $projectPath).Name
Write-Host "📂 Proyecto: $projectName en $projectPath" -ForegroundColor Cyan

# Verificar si ya existe un entorno virtual para este proyecto
try {
    $venvPath = pipenv --venv 2>&1
    if ($LASTEXITCODE -eq 0 -and (Test-Path $venvPath)) {
        Write-Host "✅ Entorno virtual encontrado: $venvPath" -ForegroundColor Green
        $venvExists = $true
    } else {
        $venvExists = $false
    }
} catch {
    $venvExists = $false
}

# Instalar dependencias desde requirements.txt
if ($venvExists) {
    Write-Host "  Instalando dependencias desde requirements.txt..." -ForegroundColor Cyan
    pipenv install -r requirements.txt
} else {
    Write-Host "📦 Instalando dependencias y creando entorno..." -ForegroundColor Cyan
    pipenv install -r requirements.txt
    # Obtener la ruta del entorno después de crearlo
    $venvPath = pipenv --venv 2>&1
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error instalando dependencias" -ForegroundColor Red
    Read-Host "Presione Enter para salir"
    exit 1
}

Write-Host ""
Write-Host "🗂️  Entorno virtual: $venvPath" -ForegroundColor Gray
Write-Host ""
Write-Host "Presione Ctrl+C para detener el servidor" -ForegroundColor Yellow
Write-Host ""

# Ejecutar el servidor usando pipenv
pipenv run python rdp.py

Write-Host ""
Write-Host "Servidor detenido." -ForegroundColor Yellow
Write-Host ""
Write-Host "💡 Para entrar manualmente al entorno: pipenv shell" -ForegroundColor Gray
Write-Host "💡 Para ver la ubicación del entorno: pipenv --venv" -ForegroundColor Gray
Read-Host "Presione Enter para salir"
