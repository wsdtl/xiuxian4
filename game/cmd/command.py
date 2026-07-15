"""游戏命令注册包装。"""

from __future__ import annotations

from typing import Any, Callable

from launch.adapter import MessageHandler

from .reply_intents import reply_intents as reply_intent_registry


GAME_METADATA_KEY = "game"
GAME_ACCESS_PUBLIC = "public"
GAME_ACCESS_PLAYER = "player"
GAME_ACCESS_VALUES = frozenset({GAME_ACCESS_PUBLIC, GAME_ACCESS_PLAYER})


class GameCommand:
    """统一游戏命令的默认注册参数和访问级别。"""

    @staticmethod
    def handler(
        *args,
        access: str = GAME_ACCESS_PLAYER,
        metadata: dict[str, Any] | None = None,
        priority: int = 100,
        block: bool = True,
        intent_ids: tuple[str, ...] = (),
        **kwargs,
    ) -> Callable:
        """注册游戏命令；默认附加 player 访问级别。"""

        normalized_access = str(access or "").strip().lower()
        if normalized_access not in GAME_ACCESS_VALUES:
            raise ValueError(f"未知游戏命令访问级别: {access}")

        merged_metadata = dict(metadata or {})
        game_metadata = dict(merged_metadata.get(GAME_METADATA_KEY) or {})
        game_metadata["access"] = normalized_access
        merged_metadata[GAME_METADATA_KEY] = game_metadata
        if intent_ids:
            command = kwargs.get("cmd")
            if isinstance(command, (tuple, list)):
                command = command[0] if command else ""
            normalized_command = str(command or "").strip()
            if not normalized_command:
                raise ValueError("回复意图只能绑定显式 cmd 命令")
            for intent_id in intent_ids:
                reply_intent_registry.register_command(intent_id, normalized_command)
        return MessageHandler.handler(
            *args,
            priority=priority,
            block=block,
            metadata=merged_metadata,
            **kwargs,
        )


__all__ = ["GameCommand"]
