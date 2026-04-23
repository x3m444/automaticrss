#!/bin/bash
# AutomaticRSS — script instalare Linux
# Utilizare:
#   ./install.sh                          # mod interactiv
#   ./install.sh --db-host db.supabase.co --db-user postgres --db-pass SECRET \
#                --download-dir /media/downloads --tr-host localhost --tr-port 9091

set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✔ $1${NC}"; }
info() { echo -e "${CYAN}▸ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
err()  { echo -e "${RED}✘ $1${NC}"; exit 1; }

# ── Argumente CLI ─────────────────────────────────────────────────────────────
DB_HOST=""; DB_PORT="5432"; DB_NAME="postgres"; DB_USER=""; DB_PASS=""
TR_HOST="localhost"; TR_PORT="9091"; TR_USER=""; TR_PASS=""
DOWNLOAD_DIR=""; APP_PORT="8080"; INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="automaticrss"

while [[ $# -gt 0 ]]; do
    case $1 in
        --db-host)      DB_HOST="$2";      shift 2 ;;
        --db-port)      DB_PORT="$2";      shift 2 ;;
        --db-name)      DB_NAME="$2";      shift 2 ;;
        --db-user)      DB_USER="$2";      shift 2 ;;
        --db-pass)      DB_PASS="$2";      shift 2 ;;
        --tr-host)      TR_HOST="$2";      shift 2 ;;
        --tr-port)      TR_PORT="$2";      shift 2 ;;
        --tr-user)      TR_USER="$2";      shift 2 ;;
        --tr-pass)      TR_PASS="$2";      shift 2 ;;
        --download-dir) DOWNLOAD_DIR="$2"; shift 2 ;;
        --app-port)     APP_PORT="$2";     shift 2 ;;
        --dir)          INSTALL_DIR="$2";  shift 2 ;;
        *) warn "Argument necunoscut: $1"; shift ;;
    esac
done

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        AutomaticRSS — Instalare          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Detectare package manager ─────────────────────────────────────────────────
if   command -v apt-get &>/dev/null; then PKG=apt
elif command -v dnf     &>/dev/null; then PKG=dnf
elif command -v yum     &>/dev/null; then PKG=yum
elif command -v pacman  &>/dev/null; then PKG=pacman
else err "Nu am găsit un package manager cunoscut (apt/dnf/yum/pacman)."; fi
ok "Package manager: $PKG"

# ── Instalare dependențe sistem ───────────────────────────────────────────────
info "Instalez dependențe sistem..."
case $PKG in
    apt)
        sudo apt-get update -qq
        sudo apt-get install -y python3 python3-venv python3-pip \
             transmission-daemon git gcc libxml2-dev libxslt-dev
        ;;
    dnf|yum)
        sudo $PKG install -y python3 python3-venv python3-pip \
             transmission-daemon git gcc libxml2-devel libxslt-devel
        ;;
    pacman)
        sudo pacman -Sy --noconfirm python python-pip transmission-cli git gcc libxml2 libxslt
        ;;
esac
ok "Dependențe instalate."

# ── Verificare Python 3.10+ ───────────────────────────────────────────────────
PY=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo $PY | cut -d. -f1); PY_MINOR=$(echo $PY | cut -d. -f2)
[[ $PY_MAJOR -ge 3 && $PY_MINOR -ge 10 ]] || err "Necesită Python 3.10+, găsit: $PY"
ok "Python $PY"

# ── Virtual environment ───────────────────────────────────────────────────────
cd "$INSTALL_DIR"
info "Creez virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
ok "Pachete Python instalate."

# ── Configurare DB (interactiv dacă lipsesc argumente) ────────────────────────
echo ""
echo -e "${CYAN}── Configurare bază de date Supabase ──${NC}"

[[ -z "$DB_HOST" ]] && read -rp "  DB Host (ex: db.xxx.supabase.co): "    DB_HOST
[[ -z "$DB_USER" ]] && read -rp "  DB User [postgres]: "                  DB_USER && DB_USER="${DB_USER:-postgres}"
[[ -z "$DB_PASS" ]] && read -rsp " DB Password: "                         DB_PASS && echo ""
[[ -z "$DB_NAME" ]] && read -rp "  DB Name [postgres]: "                  TMP && DB_NAME="${TMP:-postgres}"

mkdir -p "$INSTALL_DIR/.secrets"
cat > "$INSTALL_DIR/.secrets/secrets.toml" <<EOF
DB_HOST = "$DB_HOST"
DB_PORT = "$DB_PORT"
DB_NAME = "$DB_NAME"
DB_USER = "$DB_USER"
DB_PASS = "$DB_PASS"
EOF
chmod 600 "$INSTALL_DIR/.secrets/secrets.toml"
ok "secrets.toml creat."

# ── Configurare Transmission ──────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── Configurare Transmission ──${NC}"

[[ -z "$DOWNLOAD_DIR" ]] && read -rp "  Director descărcări [/var/lib/transmission-daemon/downloads]: " DOWNLOAD_DIR
DOWNLOAD_DIR="${DOWNLOAD_DIR:-/var/lib/transmission-daemon/downloads}"
[[ -z "$TR_HOST" ]]     && read -rp "  Transmission host [localhost]: " TMP && TR_HOST="${TMP:-localhost}"
[[ -z "$TR_PORT" ]]     && read -rp "  Transmission port [9091]: "     TMP && TR_PORT="${TMP:-9091}"
read -rp "  Transmission user (Enter pentru niciunul): " TR_USER
[[ -n "$TR_USER" ]] && read -rsp " Transmission password: " TR_PASS && echo ""

# Creare director dacă nu există
sudo mkdir -p "$DOWNLOAD_DIR"
sudo chown "$USER:$USER" "$DOWNLOAD_DIR" 2>/dev/null || true
ok "Director descărcări: $DOWNLOAD_DIR"

# Configurare transmission-daemon să folosească același director
if command -v transmission-daemon &>/dev/null; then
    sudo systemctl stop transmission-daemon 2>/dev/null || true
    TCONF="/etc/transmission-daemon/settings.json"
    [[ ! -f "$TCONF" ]] && TCONF="/var/lib/transmission-daemon/info/settings.json"
    if [[ -f "$TCONF" ]]; then
        sudo python3 -c "
import json, sys
with open('$TCONF') as f: c = json.load(f)
c['download-dir'] = '$DOWNLOAD_DIR'
c['rpc-whitelist-enabled'] = False
c['rpc-authentication-required'] = $([ -n "$TR_USER" ] && echo 'True' || echo 'False')
$([ -n "$TR_USER" ] && echo "c['rpc-username'] = '$TR_USER'; c['rpc-password'] = '$TR_PASS'")
with open('$TCONF', 'w') as f: json.dump(c, f, indent=4)
print('settings.json actualizat')
"
    fi
    # Adaugă userul curent în grupul debian-transmission pentru acces la fișiere
    sudo usermod -aG debian-transmission "$USER" 2>/dev/null || \
    sudo usermod -aG transmission "$USER" 2>/dev/null || true
    sudo systemctl enable transmission-daemon
    sudo systemctl start transmission-daemon
    ok "Transmission configurat și pornit."
fi

# ── Migrări DB ────────────────────────────────────────────────────────────────
info "Rulare migrări Alembic..."
venv/bin/python -m alembic upgrade head
ok "Schema DB actualizată."

# ── Salvare setări Transmission în DB ────────────────────────────────────────
info "Salvare setări Transmission în baza de date..."
venv/bin/python - <<PYEOF
from core.db import Session, Setting

def upsert(s, key, val):
    row = s.query(Setting).filter_by(key=key).first()
    if row: row.value = val
    else: s.add(Setting(key=key, value=val))

with Session() as s:
    upsert(s, "transmission_host", "$TR_HOST")
    upsert(s, "transmission_port", "$TR_PORT")
    upsert(s, "transmission_user", "$TR_USER")
    upsert(s, "transmission_pass", "$TR_PASS")
    upsert(s, "transmission_download_dir", "$DOWNLOAD_DIR")
    s.commit()
print("OK")
PYEOF
ok "Setări Transmission salvate în DB."

# ── Systemd service ───────────────────────────────────────────────────────────
echo ""
read -rp "Instalez ca serviciu systemd (pornire automată la boot)? [Y/n]: " INSTALL_SVC
INSTALL_SVC="${INSTALL_SVC:-Y}"

if [[ "$INSTALL_SVC" =~ ^[Yy]$ ]]; then
    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=AutomaticRSS — automatizare torrente
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python main.py
Restart=always
RestartSec=15
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
    sudo systemctl start  "$SERVICE_NAME"
    ok "Serviciu $SERVICE_NAME pornit."
    info "Status: sudo systemctl status $SERVICE_NAME"
    info "Loguri: sudo journalctl -u $SERVICE_NAME -f"
else
    # Script de pornire manuală
    cat > "$INSTALL_DIR/start.sh" <<EOF
#!/bin/bash
cd "$INSTALL_DIR"
source venv/bin/activate
exec python main.py
EOF
    chmod +x "$INSTALL_DIR/start.sh"
    ok "Script pornire creat: ./start.sh"
fi

# ── Rezumat ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Instalare completă! ✔            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Interfață web:  ${CYAN}http://localhost:$APP_PORT${NC}"
echo -e "  Transmission:   ${CYAN}http://$TR_HOST:$TR_PORT${NC}"
echo -e "  Descărcări:     ${CYAN}$DOWNLOAD_DIR${NC}"
echo ""
warn "Notă: dacă e prima conectare, re-loghează-te pentru a aplica apartenența la grupul transmission."
echo ""
