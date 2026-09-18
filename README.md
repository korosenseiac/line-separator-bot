# 🎬 Telegram Video Line Separator Bot

A high-performance, aesthetic Telegram bot designed to automatically place sleek, premium line separations above and below video posts and forwarded videos in your Telegram groups.

```text
Videos are forwarded or uploaded to your group...
✦ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ✦
[ Video 1 ]
✦ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ✦
[ Video 2 ]
✦ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ✦
```

---

## ✨ Features

- **🎯 Video-Only Targeting**: Only triggers on video uploads and forwards (`.mp4`, `.mkv`, `.mov`, round video notes, GIFs/animations, and video documents). Regular text and images are untouched.
- **✨ Intelligent Separator Flow**: Eliminates clumsy duplicate lines when multiple videos are posted consecutively. Only a single elegant separator appears between back-to-back videos.
- **📦 Album & Media Group Debounce**: If someone sends or forwards an album of 3 or 4 videos at once, they are cleanly grouped inside one top line and one bottom line.
- **🎨 Premium Preset Styles**: Choose between several curated aesthetic styles or define your own custom borders.
- **⚡ Zero Loss Quality**: Uses Telegram's instant `copy_message` API—videos are not downloaded or re-compressed on your server.
- **🚀 1-Click VPS Installer**: Automated bash script sets up Python, dependencies, and `systemd` background service in under 60 seconds.
- **🔄 Keep Running 24/7**: Configured as a Linux `systemd` service that keeps running even after you exit your SSH terminal, and auto-restarts on server reboot or crashes.
- **⚡ Automated CI/CD**: Push updates to GitHub, and GitHub Actions automatically updates and restarts the bot on your VPS with zero downtime.

---

## 🎨 Separator Styles Showcase

You can preview and change styles at any time inside Telegram using `/style <name>`:

| Style Name | Separator Preview |
| :--- | :--- |
| `luxury_gold` (Default) | `✦ ━━━━━━━━━━━━━━━━━━━━ ✦` |
| `minimal_sleek` | `━━━━━━━━━━━━━━━━━━━━━━━━━━━━` |
| `diamond_dots` | `◈ ════════════════════ ◈` |
| `modern_bar` | `▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬` |
| `aesthetic_stars` | `⋆｡°✩ ━━━━━━━━━━━━━━━━━ ✩°｡⋆` |
| `glowing_neon` | `─── ･ ｡ﾟ☆: *.☽ .* :☆ﾟ. ───` |
| `clean_double` | `════════════════════════════` |
| `tribal_flair` | `─── ❖ ── ✦ ── ❖ ───` |
| `custom` | Defined by `CUSTOM_SEPARATOR_TOP` / `CUSTOM_SEPARATOR_BOTTOM` in `.env` |

---

## 🤖 Step 1: Telegram Setup

1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to get your **Bot Token** (e.g. `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
3. Add your new bot to your Telegram Group.
4. **Grant Administrator Rights**:
   - Go to Group Settings ➔ Administrators ➔ Add Admin ➔ Select your bot.
   - Ensure **Delete Messages** and **Send Messages** permissions are enabled.
   *(Note: Delete Messages permission is required so the bot can cleanly place the top separator before the video).*

---

## ⚡ Step 2: 1-Click VPS Installation

Connect to your VPS via SSH and run the following command:

### If cloning from your GitHub repository:
```bash
git clone https://github.com/korosenseiac/line-separator-bot.git /opt/line-separator-bot
cd /opt/line-separator-bot
sudo bash install.sh
```

### What the installer does automatically:
1. Installs Python 3, pip, git, and virtual environment tools.
2. Creates the project environment at `/opt/line-separator-bot`.
3. Installs dependencies from `requirements.txt`.
4. Prompts you for your Telegram Bot Token and configures `.env`.
5. Creates, registers, and starts the `line-separator-bot` **systemd** service.
6. Verifies that the bot is running in the background.

---

## 🛠️ Managing the Bot on VPS

Because the bot runs as a **systemd service**, it stays running 24/7 even after you close your SSH terminal window.

```bash
# Check real-time live logs
sudo journalctl -u line-separator-bot -f

# Check service status
sudo systemctl status line-separator-bot

# Restart the bot
sudo systemctl restart line-separator-bot

# Stop the bot
sudo systemctl stop line-separator-bot

# Start the bot
sudo systemctl start line-separator-bot

# Edit configuration
nano /opt/line-separator-bot/.env
sudo systemctl restart line-separator-bot
```

---

## 🔄 Manual Bot Updates (If Not Using CI/CD)

If you have not configured GitHub Actions CI/CD yet, you have two quick ways to update the bot whenever you push new changes to GitHub:

### Option A: Directly inside Telegram (`/update`)
1. Add your Telegram user ID to `/opt/line-separator-bot/.env`:
   ```bash
   OWNER_ID=123456789
   ```
2. In your group or in private chat with the bot, simply type:
   ```text
   /update
   ```
3. The bot will automatically pull the latest changes from GitHub, update dependencies, report the latest commit, and reload itself!

### Option B: From VPS Terminal (`update-bot`)
Simply run this one command in your VPS terminal:
```bash
sudo update-bot
```
*(Or `sudo /opt/line-separator-bot/update.sh`)*

It automatically pulls git changes, updates dependencies, and restarts the service!

---

## 🚀 Step 3: Easy CI/CD (Auto-Deploy on Git Push)

Every time you push new code or styles to GitHub, GitHub Actions will automatically log in to your VPS, pull the latest changes, update dependencies, and restart the bot.

### How to set up CI/CD in 2 minutes:

1. Push this repository to your GitHub account:
   ```bash
   git init
   git add .
   git commit -m "feat: initial commit of video separator bot"
   git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO>.git
   git branch -M main
   git push -u origin main
   ```

2. Generate an SSH key on your local computer or VPS (if you don't already have one):
   ```bash
   ssh-keygen -t ed25519 -C "github-actions-deploy"
   ```
   Add the public key (`~/.ssh/id_ed25519.pub`) to your VPS's `~/.ssh/authorized_keys`.

3. In your GitHub Repository:
   - Go to **Settings** ➔ **Secrets and variables** ➔ **Actions**.
   - Click **New repository secret** and add:
     - `VPS_HOST`: Your VPS IP address (e.g. `123.45.67.89`)
     - `VPS_USERNAME`: Your VPS username (e.g. `root` or `ubuntu`)
     - `VPS_SSH_KEY`: The contents of your private SSH key (`~/.ssh/id_ed25519`)
     - `VPS_PORT`: (Optional, defaults to `22` if omitted)

4. **That's it!** Whenever you run:
   ```bash
   git push origin main
   ```
   GitHub Actions will automatically update your bot on your VPS and restart it with zero downtime.

---

## ⚙️ Configuration Reference (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `BOT_TOKEN` | *Required* | Telegram bot token from @BotFather |
| `BOT_MODE` | `repost` | `repost` (deletes original & places top + bottom lines) or `append` (leaves original & only posts bottom line) |
| `SEPARATOR_STYLE` | `luxury_gold` | Active separator preset name |
| `CUSTOM_SEPARATOR_TOP` | `━━━...` | Top line if `SEPARATOR_STYLE=custom` |
| `CUSTOM_SEPARATOR_BOTTOM` | `━━━...` | Bottom line if `SEPARATOR_STYLE=custom` |
| `ALLOWED_CHAT_IDS` | *(empty)* | Optional comma-separated list of group chat IDs to restrict bot usage |
| `OWNER_ID` | *(empty)* | Telegram user ID authorized to run `/update` command |
| `ADMIN_USER_IDS` | *(empty)* | Additional Telegram user IDs authorized to run `/update` |
| `INCLUDE_ANIMATIONS` | `true` | Include GIFs and MP4 animations |
| `INCLUDE_VIDEO_DOCUMENTS`| `true` | Include video files sent as documents (.mp4, .mkv, etc.) |
| `INCLUDE_VIDEO_NOTES` | `true` | Include round video bubble notes |
| `MEDIA_GROUP_DEBOUNCE_SEC`| `1.2` | Seconds to wait to group multiple album videos together |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## 💬 Bot In-Chat Commands

- `/start` - Displays bot info, current style preview, and instructions.
- `/help` - Displays command list and configuration tips.
- `/style` - Shows a live preview of all available separator styles.
- `/style <name>` - Switches the separator style for the current group (Group Admins only).
- `/status` - Diagnostic report showing whether the bot has required admin rights and is operational.
- `/update` - Pulls latest code from GitHub and reloads the bot service (Bot Owner only).

---

## 🐳 Optional: Running with Docker

If you prefer Docker over systemd:

```bash
# Build and run container with restart: always
docker compose up -d --build

# View logs
docker compose logs -f

# Restart container
docker compose restart
```

---

## 📄 License
MIT License. Free to use, modify, and distribute.
