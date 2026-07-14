"""一账号一角色与角色名称来源策略测试。"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.rules.character import (  # noqa: E402
    CHARACTERS_PER_ACCOUNT,
    CharacterIdentityPolicy,
    CharacterIdentityViolation,
    CharacterNameSource,
)


def main() -> None:
    policy = CharacterIdentityPolicy()
    assert CHARACTERS_PER_ACCOUNT == 1

    requested = policy.prepare_creation(
        account_id="account-a",
        requested_name="  自定义  名称  ",
        platform_name="QQ 昵称",
    )
    assert requested.name == "自定义 名称"
    assert requested.name_source is CharacterNameSource.REQUESTED

    platform = policy.prepare_creation(
        account_id="account-b",
        platform_name="  QQ  昵称  ",
    )
    assert platform.name == "QQ 昵称"
    assert platform.name_source is CharacterNameSource.PLATFORM

    _assert_rejected(
        "character.account_already_has_character",
        lambda: policy.prepare_creation(
            account_id="account-a",
            requested_name="第二角色",
            existing_character_ids=("character-a",),
        ),
    )
    _assert_rejected(
        "character.name_required",
        lambda: policy.prepare_creation(account_id="account-c"),
    )
    _assert_rejected(
        "character.name_invalid",
        lambda: policy.prepare_creation(
            account_id="account-d",
            requested_name="名" * 25,
        ),
    )
    print("character identity policy tests passed")


def _assert_rejected(code: str, action) -> None:
    try:
        action()
        raise AssertionError(f"角色身份策略应当拒绝：{code}")
    except CharacterIdentityViolation as exc:
        assert exc.code == code


if __name__ == "__main__":
    main()
