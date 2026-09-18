"""Separator style catalog and helpers for Telegram Video Line Separator Bot."""

from typing import Dict, Tuple

# Pre-defined aesthetic styles (Top Separator, Bottom Separator)
STYLE_PRESETS: Dict[str, Tuple[str, str]] = {
    "luxury_gold": (
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦",
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦",
    ),
    "minimal_sleek": (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ),
    "diamond_dots": (
        "◈ ════════════════════ ◈",
        "◈ ════════════════════ ◈",
    ),
    "modern_bar": (
        "▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬",
        "▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬",
    ),
    "aesthetic_stars": (
        "⋆｡°✩ ━━━━━━━━━━━━━━━━━ ✩°｡⋆",
        "⋆｡°✩ ━━━━━━━━━━━━━━━━━ ✩°｡⋆",
    ),
    "glowing_neon": (
        "─── ･ ｡ﾟ☆: *.☽ .* :☆ﾟ. ───",
        "─── ･ ｡ﾟ☆: *.☽ .* :☆ﾟ. ───",
    ),
    "clean_double": (
        "════════════════════════════",
        "════════════════════════════",
    ),
    "tribal_flair": (
        "─── ❖ ── ✦ ── ❖ ───",
        "─── ❖ ── ✦ ── ❖ ───",
    ),
}

DEFAULT_FALLBACK_STYLE = "luxury_gold"


def get_separators(
    style_name: str,
    custom_top: str = "",
    custom_bottom: str = "",
) -> Tuple[str, str]:
    """Return (top_line, bottom_line) for given style name."""
    normalized = style_name.strip().lower()
    if normalized == "custom":
        top = custom_top if custom_top else STYLE_PRESETS[DEFAULT_FALLBACK_STYLE][0]
        bottom = custom_bottom if custom_bottom else STYLE_PRESETS[DEFAULT_FALLBACK_STYLE][1]
        return top, bottom

    if normalized in STYLE_PRESETS:
        return STYLE_PRESETS[normalized]

    return STYLE_PRESETS[DEFAULT_FALLBACK_STYLE]


def get_available_styles() -> Dict[str, Tuple[str, str]]:
    """Return dictionary of all available pre-set styles."""
    return dict(STYLE_PRESETS)
