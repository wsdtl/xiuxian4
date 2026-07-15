"""游戏回复中的稳定交互意图注册表。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import re

from message import CommandLink, rich
from message.schema import Text


PENDING_ACTIONS_INTENT = "reply.pending_actions"
NOTIFICATIONS_INTENT = "reply.notifications"
WORLD_EVENTS_INTENT = "reply.world_events"
WORLD_EVENT_DETAIL_INTENT = "reply.world_event_detail"
_INTENT_ID = re.compile(r"^[a-z][a-z0-9_.-]*$")
IntentResolver = Callable[[Mapping[str, object]], str]


@dataclass(frozen=True)
class ReplyIntentDefinition:
    """把稳定交互意图解析为当前游戏命令。"""

    id: str
    resolver: IntentResolver
    submit: bool = True
    reply: bool = False

    def command(self, payload: Mapping[str, object] | None = None) -> str:
        command = str(self.resolver(dict(payload or {})) or "").strip()
        if not command:
            raise ValueError(f"回复意图 {self.id} 解析出了空命令")
        return command


class ReplyIntentRegistry:
    """集中管理通栏和通知动作，不让领域数据保存聊天命令。"""

    def __init__(self) -> None:
        self._definitions: dict[str, ReplyIntentDefinition] = {}

    def register(
        self,
        intent_id: object,
        resolver: IntentResolver,
        *,
        submit: bool = True,
        reply: bool = False,
    ) -> ReplyIntentDefinition:
        normalized_id = _intent_id(intent_id)
        definition = ReplyIntentDefinition(
            normalized_id,
            resolver,
            bool(submit),
            bool(reply),
        )
        previous = self._definitions.get(normalized_id)
        if previous is not None:
            if previous == definition:
                return previous
            raise ValueError(f"回复意图重复注册: {normalized_id}")
        self._definitions[normalized_id] = definition
        return definition

    def register_command(
        self,
        intent_id: object,
        command: object,
        *,
        submit: bool = True,
        reply: bool = False,
    ) -> ReplyIntentDefinition:
        normalized_command = str(command or "").strip()
        if not normalized_command:
            raise ValueError("回复意图命令不能为空")

        def resolve(_: Mapping[str, object]) -> str:
            return normalized_command

        previous = self._definitions.get(_intent_id(intent_id))
        if previous is not None:
            if (
                previous.command() == normalized_command
                and previous.submit is bool(submit)
                and previous.reply is bool(reply)
            ):
                return previous
            raise ValueError(f"回复意图重复注册: {previous.id}")
        return self.register(
            intent_id,
            resolve,
            submit=submit,
            reply=reply,
        )

    def definition(self, intent_id: object) -> ReplyIntentDefinition | None:
        return self._definitions.get(_intent_id(intent_id))

    def link(
        self,
        label: object,
        intent_id: object,
        payload: Mapping[str, object] | None = None,
    ) -> Text | CommandLink:
        text = str(label or "").strip()
        if not text:
            raise ValueError("回复意图链接缺少展示文本")
        definition = self.definition(intent_id)
        if definition is None:
            return Text(text)
        return CommandLink(
            rich(text),
            definition.command(payload),
            submit=definition.submit,
            reply=definition.reply,
        )

    def __contains__(self, intent_id: object) -> bool:
        return self.definition(intent_id) is not None


def _intent_id(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if _INTENT_ID.fullmatch(normalized) is None:
        raise ValueError(f"回复意图 ID 不合法: {normalized or '<empty>'}")
    return normalized


reply_intents = ReplyIntentRegistry()


__all__ = [
    "NOTIFICATIONS_INTENT",
    "PENDING_ACTIONS_INTENT",
    "ReplyIntentDefinition",
    "ReplyIntentRegistry",
    "WORLD_EVENT_DETAIL_INTENT",
    "WORLD_EVENTS_INTENT",
    "reply_intents",
]
