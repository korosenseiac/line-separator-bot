#!/usr/bin/env bash
# ==============================================================================
# Telegram Video Line Separator Bot - 1-Click VPS Auto-Installer
# ==============================================================================
# Usage:
#   curl -sSL https://raw.githubusercontent.com/<USERNAME>/<REPO>/main/install.sh | bash
# Or:
#   chmod +x install.sh && sudo ./install.sh
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

INSTALL_DIR="/opt/line-separator-bot"
SERVICE_NAME="line-separator-bot"

echo -e "${CYAN}======================================================${NC}"
echo -e "${CYAN}  Telegram Video Line Separator Bot - 1-Click Setup   ${NC}"
echo -e "${CYAN}======================================================${NC}"

# Check root / sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] Please run this script as root or with sudo.${NC}"
    exit 1
fi

echo -e "\n${BLUE}[1/6] Detecting operating system and installing dependencies...${NC}"
if command -v apt-get &>/dev/null; then
    apt-get update -y
    apt-get install -y python3 python3-pip python3-venv git curl
elif command -v dnf &>/dev/null; then
    dnf install -y python3 python3-pip python3-virtualenv git curl
elif command -v yum &>/dev/null; then
    yum install -y python3 python3-pip git curl
else
    echo -e "${YELLOW}[WARN] Unknown package manager. Please ensure python3, pip, venv, and git are installed.${NC}"
fi

echo -e "\n${BLUE}[2/6] Setting up project directory at ${INSTALL_DIR}...${NC}"
# Determine if running from an existing clone or need to copy/clone
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
    # If the script is run from a cloned folder, copy files over
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        echo -e "Copying project files from current directory..."
        cp -r "$SCRIPT_DIR/"* "$INSTALL_DIR/"
        # also copy hidden files like .env.example, .gitignore
        cp -r "$SCRIPT_DIR/".[!.]* "$INSTALL_DIR/" 2>/dev/null || true
    fi
fi

cd "$INSTALL_DIR"

echo -e "\n${BLUE}[3/6] Configuring Python virtual environment...${NC}"
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi

"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

echo -e "\n${BLUE}[4/6] Setting up configuration (.env)...${NC}"
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo -e "${YELLOW}Please enter your Telegram Bot Token from @BotFather:${NC}"
    read -p "Bot Token: " USER_TOKEN
    if [ -n "$USER_TOKEN" ]; then
        sed -i "s|^BOT_TOKEN=.*|BOT_TOKEN=$USER_TOKEN|" "$INSTALL_DIR/.env"
        echo -e "${GREEN}Bot token saved to .env${NC}"
    else
        echo -e "${RED}No token entered! Please edit $INSTALL_DIR/.env later before starting the bot.${NC}"
    fi
else
    echo -e "${GREEN}.env file already exists. Preserving current configuration.${NC}"
fi

echo -e "\n${BLUE}[5/6] Registering systemd background service...${NC}"
cat << 'EOF' > /etc/systemd/system/line-separator-bot.service
[Unit]
Description=Telegram Video Line Separator Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/line-separator-bot
ExecStart=/opt/line-separator-bot/venv/bin/python -m bot.main
Restart=always
RestartSec=5
EnvironmentFile=/opt/line-separator-bot/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo -e "\n${BLUE}[6/6] Verifying bot service status...${NC}"
# Make update script executable and link globally
if [ -f "$INSTALL_DIR/update.sh" ]; then
    chmod +x "$INSTALL_DIR/update.sh"
    ln -sf "$INSTALL_DIR/update.sh" /usr/local/bin/update-bot
    echo -e "${GREEN}Created global command: update-bot${NC}"
fi

sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "${GREEN}======================================================${NC}"
    echo -e "${GREEN}  SUCCESS! Bot is installed and running in background!${NC}"
    echo -e "${GREEN}======================================================${NC}"
else
    echo -e "${YELLOW}======================================================${NC}"
    echo -e "${YELLOW}  Service created, but may need your Bot Token.       ${NC}"
    echo -e "${YELLOW}  Check logs with: journalctl -u $SERVICE_NAME -n 20   ${NC}"
    echo -e "${YELLOW}======================================================${NC}"
fi

echo -e "\n${CYAN}Quick Management Commands:${NC}"
echo -e "  • Update bot anytime: ${YELLOW}update-bot${NC} (or sudo /opt/line-separator-bot/update.sh)"
echo -e "  • View live logs:     ${YELLOW}journalctl -u $SERVICE_NAME -f${NC}"
echo -e "  • Restart bot:        ${YELLOW}systemctl restart $SERVICE_NAME${NC}"
echo -e "  • Stop bot:           ${YELLOW}systemctl stop $SERVICE_NAME${NC}"
echo -e "  • Check status:       ${YELLOW}systemctl status $SERVICE_NAME${NC}"
echo -e "  • Edit config:        ${YELLOW}nano $INSTALL_DIR/.env${NC}"
echo -e ""
