"""角色个人设置与本游戏固定恢复策略。"""

from dataclasses import dataclass


AUTO_HEALTH_TRIGGER_RATIO = 0.25
AUTO_HEALTH_TARGET_RATIO = 0.55
AUTO_SPIRIT_TRIGGER_RATIO = 0.15
AUTO_SPIRIT_TARGET_RATIO = 0.45
REST_MINIMUM_SECONDS = 60
REST_FULL_RECOVERY_SECONDS = 30 * 60
REST_MINIMUM_RECOVERY_RATIO = 0.50


@dataclass(frozen=True)
class CharacterSettingsState:
    """只保存玩家选择；所有人相同的阈值不重复写入存档。"""

    character_id: str
    auto_use_medicine: bool = True
    mood_header_enabled: bool = False
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.character_id.strip():
            raise ValueError("CharacterSettingsState 缺少 character_id")
        if not isinstance(self.auto_use_medicine, bool):
            raise TypeError("auto_use_medicine 必须是布尔值")
        if not isinstance(self.mood_header_enabled, bool):
            raise TypeError("mood_header_enabled 必须是布尔值")
        if self.revision < 0:
            raise ValueError("CharacterSettingsState.revision 不能小于 0")


__all__ = [
    "AUTO_HEALTH_TARGET_RATIO",
    "AUTO_HEALTH_TRIGGER_RATIO",
    "AUTO_SPIRIT_TARGET_RATIO",
    "AUTO_SPIRIT_TRIGGER_RATIO",
    "CharacterSettingsState",
    "REST_FULL_RECOVERY_SECONDS",
    "REST_MINIMUM_RECOVERY_RATIO",
    "REST_MINIMUM_SECONDS",
]
