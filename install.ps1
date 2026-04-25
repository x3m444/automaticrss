#Requires -Version 5.1
<#
.SYNOPSIS
    AutomaticRSS — script instalare Windows
.DESCRIPTION
    Instalează Python, dependențele, configurează Transmission și creează un shortcut de pornire.
.PARAMETER DbHost
    Host Supabase (ex: db.xxxxx.supabase.co)
.PARAMETER DbPort
    Port PostgreSQL [5432]
.PARAMETER DbName
    Nume bază de date [postgres]
.PARAMETER DbUser
    User PostgreSQL [postgres]
.PARAMETER DbPass
    Parolă PostgreSQL
.PARAMETER TrHost
    Host Transmission [localhost]
.PARAMETER TrPort
    Port Transmission [9091]
.PARAMETER TrUser
    User Transmission (opțional)
.PARAMETER TrPass
    Parolă Transmission (opțional)
.PARAMETER DownloadDir
    Director descărcări Transmission [C:\Downloads\Torrents]
.PARAMETER AppPort
    Port aplicație web [8080]
.EXAMPLE
    .\install.ps1 -DbHost db.xxx.supabase.co -DbUser postgres -DbPass SECRET -DownloadDir D:\Torrents
#>

param(
    [string]$DbHost      = "",
    [string]$DbPort      = "5432",
    [string]$DbName      = "postgres",
    [string]$DbUser      = "",
    [string]$DbPass      = "",
    [string]$TrHost      = "localhost",
    [string]$TrPort      = "9091",
    [string]$TrUser      = "",
    [string]$TrPass      = "",
    [string]$DownloadDir = "",
    [string]$AppPort     = "8080"
)

$ErrorActionPreference = "Stop"
$InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Ok   { param($m) Write-Host "  OK  $m" -ForegroundColor Green }
function Write-Info { param($m) Write-Host "   >  $m" -ForegroundColor Cyan }
function Write-Warn { param($m) Write-Host "   !  $m" -ForegroundColor Yellow }
function Write-Err  { param($m) Write-Host "  ERR $m" -ForegroundColor Red; exit 1 }

function Prompt-If-Empty {
    param([string]$Value, [string]$Label, [string]$Default = "", [switch]$Secret)
    if ($Value -ne "") { return $Value }
    $prompt = if ($Default) { "$Label [$Default]" } else { $Label }
    if ($Secret) {
        $secure = Read-Host $prompt -AsSecureString
        return [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    }
    $input = Read-Host $prompt
    return if ($input) { $input } else { $Default }
}

Clear-Host
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║        AutomaticRSS — Instalare          ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# ── Verificare / instalare Python ─────────────────────────────────────────────
Write-Info "Verific Python..."
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Warn "Python nu e instalat. Încerc instalare via winget..."
    winget install --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pyCmd) { Write-Err "Python nu s-a instalat. Instalează manual de la python.org." }
}

$pyVer = python --version 2>&1
Write-Ok $pyVer

# ── Virtual environment ───────────────────────────────────────────────────────
Write-Info "Creez virtual environment..."
Set-Location $InstallDir
python -m venv venv
& "$InstallDir\venv\Scripts\pip" install --upgrade pip -q
& "$InstallDir\venv\Scripts\pip" install -r requirements.txt -q
Write-Ok "Pachete Python instalate."

# ── Configurare DB ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ── Configurare bază de date Supabase ──" -ForegroundColor Cyan
$DbHost = Prompt-If-Empty $DbHost "  DB Host (ex: db.xxx.supabase.co)"
$DbUser = Prompt-If-Empty $DbUser "  DB User" "postgres"
$DbPass = Prompt-If-Empty $DbPass "  DB Password" -Secret
$DbName = Prompt-If-Empty $DbName "  DB Name" "postgres"
$DbPort = Prompt-If-Empty $DbPort "  DB Port" "5432"

$InstanceId = [System.Guid]::NewGuid().ToString()
$SecretsDir = Join-Path $InstallDir ".secrets"
New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null
$SecretsContent = @"
DB_HOST = "$DbHost"
DB_PORT = "$DbPort"
DB_NAME = "$DbName"
DB_USER = "$DbUser"
DB_PASS = "$DbPass"
INSTANCE_ID = "$InstanceId"
"@
Set-Content -Path (Join-Path $SecretsDir "secrets.toml") -Value $SecretsContent -Encoding UTF8
Write-Ok "secrets.toml creat (INSTANCE_ID: $InstanceId)."

# ── Configurare Transmission ──────────────────────────────────────────────────
Write-Host ""
Write-Host "  ── Configurare Transmission ──" -ForegroundColor Cyan

if (-not $DownloadDir) {
    $DownloadDir = Prompt-If-Empty "" "  Director descărcări" "C:\Downloads\Torrents"
}
$TrHost = Prompt-If-Empty $TrHost "  Transmission host" "localhost"
$TrPort = Prompt-If-Empty $TrPort "  Transmission port" "9091"
$TrUser = Prompt-If-Empty $TrUser "  Transmission user (Enter pt. niciunul)" ""
if ($TrUser) {
    $TrPass = Prompt-If-Empty $TrPass "  Transmission password" -Secret
}

# Creează directorul de descărcări dacă nu există
New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null
Write-Ok "Director descărcări: $DownloadDir"

# ── Migrări DB ────────────────────────────────────────────────────────────────
Write-Info "Rulare migrări Alembic..."
& "$InstallDir\venv\Scripts\python" -m alembic upgrade head
Write-Ok "Schema DB actualizată."

# ── Salvare setări Transmission în DB ────────────────────────────────────────
Write-Info "Salvare setări Transmission în baza de date..."
$pyScript = @"
from core.db import Session, Setting

def upsert(s, key, val):
    row = s.query(Setting).filter_by(key=key).first()
    if row: row.value = val
    else: s.add(Setting(key=key, value=val))

with Session() as s:
    upsert(s, 'transmission_host', '$TrHost')
    upsert(s, 'transmission_port', '$TrPort')
    upsert(s, 'transmission_user', '$TrUser')
    upsert(s, 'transmission_pass', '$TrPass')
    upsert(s, 'transmission_download_dir', r'$DownloadDir')
    s.commit()
print('OK')
"@
$pyScript | & "$InstallDir\venv\Scripts\python" -
Write-Ok "Setări Transmission salvate în DB."

# ── Script de pornire ─────────────────────────────────────────────────────────
$batContent = @"
@echo off
title AutomaticRSS
cd /d "$InstallDir"
call venv\Scripts\activate.bat
echo Pornire AutomaticRSS pe http://localhost:$AppPort
python main.py
pause
"@
Set-Content -Path (Join-Path $InstallDir "start.bat") -Value $batContent -Encoding UTF8

# Shortcut pe Desktop
$WshShell  = New-Object -ComObject WScript.Shell
$Shortcut  = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\AutomaticRSS.lnk")
$Shortcut.TargetPath       = Join-Path $InstallDir "start.bat"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description      = "AutomaticRSS — automatizare torrente"
$Shortcut.Save()
Write-Ok "Shortcut creat pe Desktop."

# ── Task Scheduler (pornire la login) ────────────────────────────────────────
Write-Host ""
$installTask = Read-Host "  Pornire automată la login (Task Scheduler)? [Y/n]"
if ($installTask -notmatch '^[Nn]') {
    $action  = New-ScheduledTaskAction -Execute (Join-Path $InstallDir "start.bat")
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName "AutomaticRSS" -Action $action -Trigger $trigger `
        -Settings $settings -RunLevel Highest -Force | Out-Null
    Write-Ok "Task Scheduler configurat."
}

# ── Rezumat ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║         Instalare completă!  ✔           ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Interfață web  : http://localhost:$AppPort" -ForegroundColor Cyan
Write-Host "  Transmission   : http://${TrHost}:$TrPort" -ForegroundColor Cyan
Write-Host "  Descărcări     : $DownloadDir" -ForegroundColor Cyan
Write-Host ""
Write-Warn "Pornire manuală: dublu-click pe start.bat sau shortcut-ul de pe Desktop."
Write-Host ""
