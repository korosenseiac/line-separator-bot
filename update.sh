#!/usr/bin/env bash
# ==============================================================================
# Telegram Video Line Separator Bot - Manual Update Script
# ==============================================================================
# Usage:
#   sudo /opt/line-separator-bot/update.sh
# Or (if installed globally):
#   sudo update-bot
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
echo -e "${CYAN}  Updating Telegram Video Line Separator Bot...       ${NC}"
echo -e "${CYAN}======================================================${NC}"

# Check if directory exists
if [ ! -d "$INSTALL_DIR" ]; then
    # Fallback to current directory if not in /opt
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        INSTALL_DIR="$SCRIPT_DIR"
    else
        echo -e "${RED}[ERROR] Project directory $INSTALL_DIR not found.${NC}"
        exit 1
    fi
fi

cd "$INSTALL_DIR"

echo -e "\n${BLUE}[1/4] Pulling latest updates from GitHub...${NC}"
if [ -d ".git" ]; then
    CURRENT_BRANCH=$(git branch --show-current || echo "main")
    git fetch origin "$CURRENT_BRANCH" || git fetch origin master || true
    git reset --hard "origin/$CURRENT_BRANCH" || git pull origin "$CURRENT_BRANCH" || true
    echo -e "${GREEN}Current Commit:${NC} $(git log -1 --oneline)"
else
    echo -e "${YELLOW}[WARN] .git directory not found. Skipping git pull.${NC}"
fi

echo -e "\n${BLUE}[2/4] Updating Python dependencies...${NC}"
if [ -d "$INSTALL_DIR/venv" ]; then
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
    echo -e "${GREEN}Dependencies up to date.${NC}"
else
    echo -e "${YELLOW}[WARN] Virtualenv not found. Skipping pip install.${NC}"
fi

echo -e "\n${BLUE}[3/4] Restarting systemd service...${NC}"
if systemctl list-unit-files | grep -q "^$SERVICE_NAME.service"; then
    sudo systemctl restart "$SERVICE_NAME"
    sleep 2
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}Service $SERVICE_NAME restarted successfully!${NC}"
    else
        echo -e "${RED}[ERROR] Service failed to restart. Check logs: journalctl -u $SERVICE_NAME -n 20${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}[WARN] systemd service $SERVICE_NAME not registered.${NC}"
fi

echo -e "\n${BLUE}[4/4] Verification & Status${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}  UPDATE COMPLETED SUCCESSFULLY!                      ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "Live logs: ${YELLOW}sudo journalctl -u $SERVICE_NAME -f${NC}\n"
