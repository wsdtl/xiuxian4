"""公共消息图标分类。

组件只传 icon key，不直接传展示字符；新增分类只需要扩展这张表。
"""

SECTION_ICONS: dict[str, str] = {
    "guide": "📜",
    "help": "📜",
    "docs": "📜",
    "encyclopedia": "📚",
    "history": "📜",
    "news": "📰",
    "log": "📄",
    "status": "🌱",
    "player": "🌱",
    "profile": "🌱",
    "notice": "📌",
    "system": "✨",
    "mood": "🎐",
    "map": "🗺️",
    "location": "🗺️",
    "navigation": "🧭",
    "trade": "💰",
    "market": "💰",
    "sell": "💰",
    "income": "💰",
    "bank": "🏦",
    "treasury": "🏛️",
    "tax": "🧾",
    "auction": "🧾",
    "inventory": "📦",
    "backpack": "🎒",
    "ring": "💍",
    "vault": "🧰",
    "item": "📦",
    "material": "🧱",
    "reward": "🎁",
    "voucher": "🎟️",
    "combat": "⚔️",
    "explore": "🥾",
    "recovery": "🌿",
    "duel": "⚔️",
    "robbery": "🗡️",
    "boss": "👑",
    "wormhole": "🌀",
    "weapon": "⚔️",
    "equipment": "🛡️",
    "gem": "💎",
    "inscription": "✒️",
    "physique": "🧬",
    "skill": "📘",
    "wish": "✨",
    "yuanqi": "💞",
    "dongtian": "🎮",
    "fishing": "🎣",
    "sect": "🏯",
    "skin": "🎭",
    "world": "🌏",
    "admin": "🧩",
    "user_group": "🧩",
    "message": "💬",
    "config": "⚙️",
    "test": "📏",
}


def icon_for(key: object) -> str:
    """按分类 key 返回图标；未知 key 立即暴露配置错误。"""

    value = str(key or "").strip()
    if not value:
        return ""
    try:
        return SECTION_ICONS[value]
    except KeyError as exc:
        raise ValueError(f"未知消息图标分类：{value}") from exc
