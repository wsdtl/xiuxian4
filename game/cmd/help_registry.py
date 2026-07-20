"""游戏命令帮助元数据与只读注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


HELP_CATEGORY_ORDER = (
    "角色",
    "行动",
    "资产",
    "世界",
    "战斗与社交",
    "活动",
)


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").split())


@dataclass(frozen=True)
class HelpSpec:
    """命令在玩家帮助中的最小公开说明。"""

    category: str
    summary: str
    usage: tuple[str, ...]
    side_effect: str = ""
    order: int = 100

    def __post_init__(self) -> None:
        category = _normalized_text(self.category)
        summary = _normalized_text(self.summary)
        usage = tuple(
            normalized
            for value in self.usage
            if (normalized := _normalized_text(value))
        )
        side_effect = _normalized_text(self.side_effect)
        if category not in HELP_CATEGORY_ORDER:
            raise ValueError(f"未知帮助分类: {self.category}")
        if not summary:
            raise ValueError("命令帮助缺少一句话用途")
        if not usage:
            raise ValueError("命令帮助至少需要一种写法")
        if int(self.order) < 0:
            raise ValueError("命令帮助顺序不能小于零")
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "summary", summary)
        object.__setattr__(self, "usage", usage)
        object.__setattr__(self, "side_effect", side_effect)
        object.__setattr__(self, "order", int(self.order))


@dataclass(frozen=True)
class CommandHelpEntry:
    """一条已经绑定真实命令的公开帮助。"""

    command: str
    aliases: tuple[str, ...]
    access: str
    spec: HelpSpec


class HelpRegistry:
    """收集命令注册时声明的帮助，不保存任何玩家状态。"""

    def __init__(self) -> None:
        self._entries: dict[str, CommandHelpEntry] = {}
        self._commands: dict[str, str] = {}

    def register(
        self,
        commands: str | Sequence[str],
        spec: HelpSpec,
        *,
        access: str,
    ) -> CommandHelpEntry:
        normalized_commands = _normalize_commands(commands)
        primary = normalized_commands[0]
        entry = CommandHelpEntry(
            command=primary,
            aliases=normalized_commands[1:],
            access=_normalized_text(access).lower(),
            spec=spec,
        )
        existing = self._entries.get(primary)
        if existing is not None:
            if existing != entry:
                raise ValueError(f"命令帮助重复且定义不一致: {primary}")
            return existing
        for command in normalized_commands:
            key = command.casefold()
            owner = self._commands.get(key)
            if owner is not None:
                raise ValueError(f"帮助命令或别名重复: {command} -> {owner}")
        self._entries[primary] = entry
        for command in normalized_commands:
            self._commands[command.casefold()] = primary
        return entry

    def find(self, command: object) -> CommandHelpEntry | None:
        """按主命令或别名精确查询。"""

        primary = self._commands.get(_normalized_text(command).casefold())
        return self._entries.get(primary) if primary is not None else None

    def categories(self) -> tuple[str, ...]:
        """按固定产品顺序返回当前有内容的分类。"""

        populated = {entry.spec.category for entry in self._entries.values()}
        return tuple(category for category in HELP_CATEGORY_ORDER if category in populated)

    def in_category(self, category: object) -> tuple[CommandHelpEntry, ...]:
        """返回分类内按显式顺序和命令名排列的帮助。"""

        normalized = _normalized_text(category)
        return tuple(
            sorted(
                (
                    entry
                    for entry in self._entries.values()
                    if entry.spec.category == normalized
                ),
                key=lambda entry: (entry.spec.order, entry.command),
            )
        )

    def entries(self) -> tuple[CommandHelpEntry, ...]:
        """返回全部公开帮助，主要供架构门禁和文档工具使用。"""

        category_order = {
            category: index for index, category in enumerate(HELP_CATEGORY_ORDER)
        }
        return tuple(
            sorted(
                self._entries.values(),
                key=lambda entry: (
                    category_order[entry.spec.category],
                    entry.spec.order,
                    entry.command,
                ),
            )
        )


def _normalize_commands(commands: str | Sequence[str]) -> tuple[str, ...]:
    values: Iterable[object]
    if isinstance(commands, str):
        values = (commands,)
    else:
        values = commands
    normalized = tuple(
        command
        for value in values
        if (command := _normalized_text(value))
    )
    if not normalized:
        raise ValueError("命令帮助只能绑定显式 cmd 命令")
    if len(normalized) != len(set(command.casefold() for command in normalized)):
        raise ValueError("同一命令帮助中不能重复声明命令或别名")
    return normalized


help_registry = HelpRegistry()


__all__ = [
    "CommandHelpEntry",
    "HELP_CATEGORY_ORDER",
    "HelpRegistry",
    "HelpSpec",
    "help_registry",
]
