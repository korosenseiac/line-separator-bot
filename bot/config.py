"""Configuration module for Telegram Video Line Separator Bot."""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Set

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _str_to_bool(val: str, default: bool = False) -> bool:
    if val is None:
        return default
    val_clean = val.strip().lower()
    if val_clean in ("true", "1", "yes", "on", "t"):
        return True
    if val_clean in ("false", "0", "no", "off", "f"):
        return False
    return default


def _parse_chat_ids(val: str) -> Set[int]:
    if not val or not val.strip():
        return set()
    result = set()
    for item in val.split(","):
        cleaned = item.strip()
        if cleaned:
            try:
                result.add(int(cleaned))
            except ValueError:
                pass
    return result


@dataclass
class BotConfig:
    bot_token: str
    bot_mode: str = "repost"  # "repost" or "append"
    separator_style: str = "luxury_gold"
    custom_separator_top: str = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    custom_separator_bottom: str = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    allowed_chat_ids: Set[int] = field(default_factory=set)
    owner_id: Optional[int] = None
    admin_user_ids: Set[int] = field(default_factory=set)
    include_animations: bool = True
    include_video_documents: bool = True
    include_video_notes: bool = True
    media_group_debounce_sec: float = 1.2
    log_level: str = "INFO"

    @classmethod
    def load_from_env(cls) -> "BotConfig":
        token = os.getenv("BOT_TOKEN", "").strip()
        mode = os.getenv("BOT_MODE", "repost").strip().lower()
        if mode not in ("repost", "append"):
            mode = "repost"

        style = os.getenv("SEPARATOR_STYLE", "luxury_gold").strip().lower()
        custom_top = os.getenv("CUSTOM_SEPARATOR_TOP", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━").strip()
        custom_bottom = os.getenv("CUSTOM_SEPARATOR_BOTTOM", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━").strip()
        allowed_ids_raw = os.getenv("ALLOWED_CHAT_IDS", "")
        allowed_chat_ids = _parse_chat_ids(allowed_ids_raw)

        owner_raw = os.getenv("OWNER_ID", "").strip()
        owner_id = int(owner_raw) if owner_raw.isdigit() or (owner_raw.startswith("-") and owner_raw[1:].isdigit()) else None

        admin_ids_raw = os.getenv("ADMIN_USER_IDS", "")
        admin_user_ids = _parse_chat_ids(admin_ids_raw)

        include_animations = _str_to_bool(os.getenv("INCLUDE_ANIMATIONS"), default=True)
        include_video_docs = _str_to_bool(os.getenv("INCLUDE_VIDEO_DOCUMENTS"), default=True)
        include_video_notes = _str_to_bool(os.getenv("INCLUDE_VIDEO_NOTES"), default=True)

        try:
            debounce_sec = float(os.getenv("MEDIA_GROUP_DEBOUNCE_SEC", "1.2").strip())
        except ValueError:
            debounce_sec = 1.2

        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()

        return cls(
            bot_token=token,
            bot_mode=mode,
            separator_style=style,
            custom_separator_top=custom_top,
            custom_separator_bottom=custom_bottom,
            allowed_chat_ids=allowed_chat_ids,
            owner_id=owner_id,
            admin_user_ids=admin_user_ids,
            include_animations=include_animations,
            include_video_documents=include_video_docs,
            include_video_notes=include_video_notes,
            media_group_debounce_sec=debounce_sec,
            log_level=log_level,
        )


# Global config instance loaded at module import time
config = BotConfig.load_from_env()
