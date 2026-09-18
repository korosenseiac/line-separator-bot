"""Message handlers and business logic for Telegram Video Line Separator Bot."""

import asyncio
import logging
from typing import Dict, List, Optional, Set

from telegram import ChatMember, Message, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from bot.config import config
from bot.styles import get_available_styles, get_separators

logger = logging.getLogger(__name__)

# In-memory runtime state per chat
# chat_id -> {"last_was_separator": bool, "style": str}
_chat_state: Dict[int, Dict] = {}


def _get_chat_state(chat_id: int) -> Dict:
    if chat_id not in _chat_state:
        _chat_state[chat_id] = {
            "last_was_separator": False,
            "style": config.separator_style,
        }
    return _chat_state[chat_id]


def is_last_separator(chat_id: int) -> bool:
    return _get_chat_state(chat_id).get("last_was_separator", False)


def set_last_separator(chat_id: int, status: bool) -> None:
    _get_chat_state(chat_id)["last_was_separator"] = status


def get_chat_style(chat_id: int) -> str:
    return _get_chat_state(chat_id).get("style", config.separator_style)


def set_chat_style(chat_id: int, style: str) -> None:
    _get_chat_state(chat_id)["style"] = style


def get_active_separators_for_chat(chat_id: int) -> tuple[str, str]:
    style = get_chat_style(chat_id)
    return get_separators(
        style_name=style,
        custom_top=config.custom_separator_top,
        custom_bottom=config.custom_separator_bottom,
    )


def is_video_message(message: Message) -> bool:
    """Determine if a message is a video post according to configuration."""
    if not message:
        return False

    # 1. Standard video post or forwarded video
    if message.video:
        return True

    # 2. Round video note
    if config.include_video_notes and message.video_note:
        return True

    # 3. Animation / GIF
    if config.include_animations and message.animation:
        return True

    # 4. Video sent as uncompressed document
    if config.include_video_documents and message.document:
        doc = message.document
        mime = (doc.mime_type or "").lower()
        file_name = (doc.file_name or "").lower()
        video_exts = (
            ".mp4", ".mkv", ".mov", ".avi", ".webm",
            ".flv", ".wmv", ".m4v", ".3gp", ".ts"
        )
        if mime.startswith("video/") or any(file_name.endswith(ext) for ext in video_exts):
            return True

    return False


def is_chat_allowed(chat_id: int) -> bool:
    """Check if the chat is allowed by ALLOWED_CHAT_IDS whitelist (if configured)."""
    if not config.allowed_chat_ids:
        return True
    return chat_id in config.allowed_chat_ids


async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if a user is an administrator or creator of the chat."""
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except Exception as e:
        logger.debug(f"Failed to check admin status for user {user_id} in chat {chat_id}: {e}")
        return False


# ==============================================================================
# Safe Telegram API wrappers
# ==============================================================================

async def _send_separator(chat_id: int, text: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a single separator line. Logs (instead of raising) on failure."""
    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logger.error(f"Error sending separator in chat {chat_id}: {e}")


async def _delete_message(
    chat_id: int,
    message_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """Delete a message, returning True only if Telegram confirmed the deletion."""
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except BadRequest as e:
        logger.warning(
            f"Cannot delete message {message_id} in chat {chat_id} ({e.message}). "
            "Ensure the bot is Admin with the 'Delete Messages' permission."
        )
        return False
    except Exception as e:
        logger.warning(f"Unexpected error deleting message {message_id} in chat {chat_id}: {e}")
        return False


async def _copy_message(
    chat_id: int,
    message_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[int]:
    """Repost (copy) a message into the same chat, returning the new message ID.

    Telegram can only copy a message that still exists, so this MUST always be
    called *before* the source message is deleted.
    """
    try:
        copied = await context.bot.copy_message(
            chat_id=chat_id,
            from_chat_id=chat_id,
            message_id=message_id,
        )
        return copied.message_id
    except Exception as e:
        logger.error(f"Could not repost message {message_id} in chat {chat_id}: {e}")
        return None


async def _copy_media_group(
    chat_id: int,
    message_ids: List[int],
    context: ContextTypes.DEFAULT_TYPE,
) -> List[int]:
    """Repost an album, returning the message IDs of the copies actually created."""
    if hasattr(context.bot, "copy_messages"):
        try:
            copied = await context.bot.copy_messages(
                chat_id=chat_id,
                from_chat_id=chat_id,
                message_ids=message_ids,
            )
            return [item.message_id for item in copied]
        except Exception as e:
            logger.warning(
                f"Batch album repost failed in chat {chat_id} ({e}). "
                "Falling back to copying the album one message at a time."
            )

    copied_ids: List[int] = []
    for message_id in message_ids:
        new_id = await _copy_message(chat_id, message_id, context)
        if new_id is not None:
            copied_ids.append(new_id)
    return copied_ids


async def _can_delete_messages(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the bot is allowed to delete other members' messages in this chat."""
    try:
        member = await context.bot.get_chat_member(chat_id, context.bot.id)
    except Exception as e:
        logger.warning(f"Could not verify bot permissions in chat {chat_id}: {e}")
        return False

    if member.status == ChatMember.OWNER:
        return True
    if member.status == ChatMember.ADMINISTRATOR:
        return bool(getattr(member, "can_delete_messages", False))
    return False


class MediaGroupCollector:
    """Buffers messages belonging to the same media group (album) and flushes them together."""

    def __init__(self):
        self._buffers: Dict[str, List[Message]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}

    def add(
        self,
        media_group_id: str,
        message: Message,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if media_group_id not in self._buffers:
            self._buffers[media_group_id] = []

        self._buffers[media_group_id].append(message)

        # Reset debounce timer
        if media_group_id in self._tasks and not self._tasks[media_group_id].done():
            self._tasks[media_group_id].cancel()

        self._tasks[media_group_id] = asyncio.create_task(
            self._flush_after_delay(media_group_id, message.chat.id, context)
        )

    async def _flush_after_delay(
        self,
        media_group_id: str,
        chat_id: int,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        try:
            await asyncio.sleep(config.media_group_debounce_sec)
        except asyncio.CancelledError:
            return

        messages = self._buffers.pop(media_group_id, [])
        self._tasks.pop(media_group_id, None)

        if not messages:
            return

        # Sort messages in chronological order
        messages.sort(key=lambda m: m.message_id)
        await process_media_group(chat_id, messages, context)


media_group_collector = MediaGroupCollector()


async def process_single_video(
    chat_id: int,
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Process a standalone video message.

    In "repost" mode the video ends up bracketed by separators:

        [top line] -> [reposted video] -> [bottom line]

    The video is reposted *before* the original message is deleted, because
    Telegram can only copy messages that still exist.
    """
    top_line, bottom_line = get_active_separators_for_chat(chat_id)
    need_top_line = not is_last_separator(chat_id)

    # "append" mode - or "repost" mode without the required admin right - keeps the
    # original video untouched and only closes it with a bottom line.
    if config.bot_mode != "repost" or not await _can_delete_messages(chat_id, context):
        await _send_separator(chat_id, bottom_line, context)
        set_last_separator(chat_id, True)
        return

    # 1. Top separator first, so it lands above the reposted video.
    if need_top_line:
        await _send_separator(chat_id, top_line, context)

    # 2. Repost the video while the original message still exists.
    copied_message_id = await _copy_message(chat_id, message.message_id, context)

    if copied_message_id is None:
        # The video could not be reposted (e.g. protected content). Never delete the
        # original in that case: keep the video and fall back to appending a line.
        await _send_separator(chat_id, bottom_line, context)
        set_last_separator(chat_id, True)
        return

    # 3. Remove the original only after the repost succeeded.
    if not await _delete_message(chat_id, message.message_id, context):
        # Deletion was refused after all: drop our own copy so the video is never
        # shown twice.
        await _delete_message(chat_id, copied_message_id, context)

    # 4. Bottom separator.
    await _send_separator(chat_id, bottom_line, context)
    set_last_separator(chat_id, True)


async def process_media_group(
    chat_id: int,
    messages: List[Message],
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Process an album of video messages grouped inside one separator pair.

    The album is reposted *before* the originals are deleted.
    """
    top_line, bottom_line = get_active_separators_for_chat(chat_id)
    need_top_line = not is_last_separator(chat_id)
    message_ids = [m.message_id for m in messages]

    # "append" mode - or "repost" mode without the required admin right - keeps the
    # original album untouched and only closes it with a bottom line.
    if config.bot_mode != "repost" or not await _can_delete_messages(chat_id, context):
        await _send_separator(chat_id, bottom_line, context)
        set_last_separator(chat_id, True)
        return

    # 1. Top separator first, so it lands above the reposted album.
    if need_top_line:
        await _send_separator(chat_id, top_line, context)

    # 2. Repost the album while the original messages still exist.
    copied_ids = await _copy_media_group(chat_id, message_ids, context)

    if len(copied_ids) == len(message_ids):
        # 3. Delete the originals only when every album item was reposted.
        all_deleted = True
        for message_id in message_ids:
            if not await _delete_message(chat_id, message_id, context):
                all_deleted = False

        if not all_deleted:
            # Roll the reposted album back so nothing is duplicated.
            for copied_id in copied_ids:
                await _delete_message(chat_id, copied_id, context)
    else:
        # An incomplete repost would silently drop videos from the album, so keep
        # the original album and remove the partial copies instead.
        logger.warning(
            f"Album repost in chat {chat_id} incomplete "
            f"({len(copied_ids)}/{len(message_ids)} items copied). Keeping the originals."
        )
        for copied_id in copied_ids:
            await _delete_message(chat_id, copied_id, context)

    # 4. Bottom separator.
    await _send_separator(chat_id, bottom_line, context)
    set_last_separator(chat_id, True)


# ==============================================================================
# Telegram Handlers
# ==============================================================================

async def handle_incoming_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main message handler. Detects videos and separates them."""
    message = update.effective_message
    if not message or not message.chat:
        return

    chat_id = message.chat.id

    # Ignore messages from the bot itself to prevent recursion
    if message.from_user and message.from_user.id == context.bot.id:
        return

    # Whitelist check
    if not is_chat_allowed(chat_id):
        return

    # If it is NOT a video post, clear the separator state
    if not is_video_message(message):
        # A normal message arrived, so future videos will need a top separator
        set_last_separator(chat_id, False)
        return

    # If it has a media group ID (album):
    if message.media_group_id:
        media_group_collector.add(message.media_group_id, message, context)
        return

    # Standalone video
    await process_single_video(chat_id, message, context)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /start command."""
    user = update.effective_user
    chat = update.effective_chat
    top_line, bottom_line = get_active_separators_for_chat(chat.id)

    welcome_text = (
        f"👋 <b>Welcome to Video Line Separator Bot</b>, {user.first_name if user else 'Friend'}!\n\n"
        "✨ I automatically add clean, premium line separators above and below videos "
        "uploaded or forwarded to your group.\n\n"
        "<b>Current Configuration:</b>\n"
        f"• Mode: <code>{config.bot_mode}</code>\n"
        f"• Active Style: <code>{get_chat_style(chat.id)}</code>\n\n"
        "<b>Style Preview:</b>\n"
        f"<code>{top_line}</code>\n"
        "🎬 <i>[Your Video Here]</i>\n"
        f"<code>{bottom_line}</code>\n\n"
        "<b>How to use:</b>\n"
        "1. Add me to your Telegram Group.\n"
        "2. Promote me to <b>Administrator</b> with <b>Delete Messages</b> & <b>Send Messages</b> permissions.\n"
        "3. Send or forward any video to the group!\n\n"
        "Type /help to see all available commands and styles."
    )
    await update.effective_message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /help command."""
    help_text = (
        "📖 <b>Video Line Separator Bot - Commands & Help</b>\n\n"
        "<b>Available Commands:</b>\n"
        "• /start - Welcome & quick overview\n"
        "• /help - Display this guide\n"
        "• /style - Preview all available line styles\n"
        "• /style &lt;name&gt; - Change line style for this chat (Admins only)\n"
        "• /status - Check bot permissions and health\n"
        "• /update - Pull latest code from GitHub & restart bot (Owner only)\n\n"
        "<b>Preset Styles:</b>\n"
        "• <code>luxury_gold</code>\n"
        "• <code>minimal_sleek</code>\n"
        "• <code>diamond_dots</code>\n"
        "• <code>modern_bar</code>\n"
        "• <code>aesthetic_stars</code>\n"
        "• <code>glowing_neon</code>\n"
        "• <code>clean_double</code>\n"
        "• <code>tribal_flair</code>\n"
        "• <code>custom</code> (configured via .env)\n\n"
        "💡 <i>Tip: For seamless top & bottom separation, make sure the bot has "
        "<b>Delete Messages</b> permission in your group!</i>"
    )
    await update.effective_message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def handle_style(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /style command. Previews or sets the separator style."""
    chat = update.effective_chat
    user = update.effective_user
    args = context.args

    presets = get_available_styles()

    # If no argument, show all available styles with live previews
    if not args:
        current_style = get_chat_style(chat.id)
        lines = [
            f"🎨 <b>Line Separator Styles</b> (Current: <code>{current_style}</code>)\n"
            "To switch style, send: <code>/style &lt;style_name&gt;</code>\n"
        ]

        for name, (top, _) in presets.items():
            active_marker = " ✅" if name == current_style else ""
            lines.append(f"• <b>{name}</b>{active_marker}:\n<code>{top}</code>\n")

        lines.append("• <b>custom</b>:\nDefined via <code>CUSTOM_SEPARATOR_TOP</code> in <code>.env</code>")
        await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    # Changing the style:
    chosen_style = args[0].strip().lower()

    # Check permission in group chats
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        if not await is_user_admin(chat.id, user.id, context):
            await update.effective_message.reply_text(
                "⚠️ Only group administrators can change the separator style.",
                parse_mode=ParseMode.HTML,
            )
            return

    if chosen_style not in presets and chosen_style != "custom":
        valid_names = ", ".join(f"<code>{s}</code>" for s in list(presets.keys()) + ["custom"])
        await update.effective_message.reply_text(
            f"❌ Unknown style <code>{chosen_style}</code>.\n\nValid choices are: {valid_names}",
            parse_mode=ParseMode.HTML,
        )
        return

    set_chat_style(chat.id, chosen_style)
    top_line, bottom_line = get_active_separators_for_chat(chat.id)

    response = (
        f"✅ <b>Separator style updated to:</b> <code>{chosen_style}</code>\n\n"
        "<b>Preview:</b>\n"
        f"<code>{top_line}</code>\n"
        "🎬 <i>[Video Post]</i>\n"
        f"<code>{bottom_line}</code>"
    )
    await update.effective_message.reply_text(response, parse_mode=ParseMode.HTML)


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /status command. Verifies bot permissions and operational status."""
    chat = update.effective_chat
    bot_member = None
    can_delete = False

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        try:
            bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
            if bot_member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
                can_delete = bool(getattr(bot_member, "can_delete_messages", False))
        except Exception as e:
            logger.warning(f"Error fetching bot member info: {e}")

    mode = config.bot_mode
    style = get_chat_style(chat.id)
    top, bottom = get_active_separators_for_chat(chat.id)

    status_lines = [
        "🤖 <b>Bot Status & Diagnostic Report</b>\n",
        f"• <b>Status:</b> 🟢 Running",
        f"• <b>Chat ID:</b> <code>{chat.id}</code>",
        f"• <b>Chat Type:</b> <code>{chat.type}</code>",
        f"• <b>Mode:</b> <code>{mode}</code>",
        f"• <b>Current Style:</b> <code>{style}</code>",
    ]

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        is_admin = bot_member and bot_member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
        status_lines.append(f"• <b>Is Bot Admin:</b> {'✅ Yes' if is_admin else '❌ No'}")
        status_lines.append(f"• <b>Can Delete Messages:</b> {'✅ Yes' if can_delete else '❌ No'}")

        if mode == "repost" and not can_delete:
            status_lines.append(
                "\n⚠️ <b>Warning:</b> Bot is in <code>repost</code> mode but does NOT have "
                "<b>Delete Messages</b> permission. It will fallback to append mode until permission is granted."
            )
    else:
        status_lines.append("• <i>(Private chat mode)</i>")

    status_lines.append(f"\n<b>Style Preview:</b>\n<code>{top}</code>\n🎬 <i>[Video]</i>\n<code>{bottom}</code>")

    await update.effective_message.reply_text("\n".join(status_lines), parse_mode=ParseMode.HTML)


async def handle_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /update command. Pulls latest git code, updates pip, and restarts service."""
    user = update.effective_user
    chat = update.effective_chat
    if not user:
        return

    # Check authorization
    is_owner = (config.owner_id is not None and user.id == config.owner_id)
    is_admin_user = (user.id in config.admin_user_ids)

    # If OWNER_ID is not configured, allow group owner if in group
    is_group_owner = False
    if config.owner_id is None and not config.admin_user_ids:
        if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            try:
                member = await context.bot.get_chat_member(chat.id, user.id)
                is_group_owner = (member.status == ChatMember.OWNER)
            except Exception:
                is_group_owner = False

    if not (is_owner or is_admin_user or is_group_owner):
        warning_msg = (
            "⛔ <b>Access Denied:</b> You are not authorized to update the bot.\n\n"
            f"Your Telegram User ID is: <code>{user.id}</code>\n"
            "To authorize yourself, set <code>OWNER_ID=" f"{user.id}</code> in your <code>.env</code> file."
        )
        await update.effective_message.reply_text(warning_msg, parse_mode=ParseMode.HTML)
        return

    status_msg = await update.effective_message.reply_text(
        "⏳ <b>Initiating bot update...</b>\nPulling latest code from GitHub repository...",
        parse_mode=ParseMode.HTML,
    )

    try:
        # 1. Git pull / fetch & reset
        proc = await asyncio.create_subprocess_shell(
            "git fetch origin && git reset --hard origin/$(git branch --show-current || echo main)",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        # 2. Get latest commit info
        log_proc = await asyncio.create_subprocess_shell(
            "git log -1 --pretty=format:'%h - %s (%an, %ar)'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        log_out, _ = await log_proc.communicate()
        latest_commit = log_out.decode().strip() or "Latest version"

        # 3. Update pip dependencies
        pip_proc = await asyncio.create_subprocess_shell(
            "pip install -r requirements.txt --quiet",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await pip_proc.communicate()

        await status_msg.edit_text(
            f"✅ <b>Update Successful!</b>\n\n"
            f"📦 <b>Commit:</b> <code>{latest_commit}</code>\n\n"
            "♻️ <b>Restarting bot service...</b> Please wait a few moments for the new version to become active.",
            parse_mode=ParseMode.HTML,
        )

        # Trigger restart
        await asyncio.sleep(1)
        try:
            await asyncio.create_subprocess_shell("sudo systemctl restart line-separator-bot")
        except Exception:
            pass

        import sys
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error during bot update: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ <b>Update Failed:</b>\n<code>{str(e)}</code>",
            parse_mode=ParseMode.HTML,
        )
