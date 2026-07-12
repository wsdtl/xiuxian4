"""本地驱动器事件。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from ..context import CONVERSATION_GROUP, CONVERSATION_PRIVATE


@dataclass(frozen=True)
class LocalCommandEvent:
    """本地驱动器内部使用的规整命令事件。"""

    event_id: str
    client_id: str
    raw_message: str
    conversation_type: str = CONVERSATION_PRIVATE
    bypass_guards: bool = False

    def __post_init__(self) -> None:
        conversation_type = str(self.conversation_type or "").strip().lower()
        if conversation_type not in {CONVERSATION_PRIVATE, CONVERSATION_GROUP}:
            raise ValueError(f"未知本地会话类型：{self.conversation_type}")
        event_id = str(self.event_id or "").strip() or f"local-{uuid4().hex}"
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "client_id", str(self.client_id or "").strip())
        object.__setattr__(self, "raw_message", str(self.raw_message or "").strip())
        object.__setattr__(self, "conversation_type", conversation_type)
        object.__setattr__(self, "bypass_guards", bool(self.bypass_guards))


def local_command_event(
    *,
    client_id: str,
    raw_message: str,
    conversation_type: str = CONVERSATION_PRIVATE,
    event_id: str = "",
    bypass_guards: bool = False,
) -> LocalCommandEvent:
    """构造本地命令事件；未传 event_id 时由驱动器生成。"""

    return LocalCommandEvent(
        event_id=event_id or f"local-{uuid4().hex}",
        client_id=client_id,
        raw_message=raw_message,
        conversation_type=conversation_type,
        bypass_guards=bypass_guards,
    )
