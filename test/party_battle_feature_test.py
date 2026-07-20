"""组队挑战业务闭环：独立首领池、准备、战斗、战报和幂等。"""

from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.app import build_game_services  # noqa: E402
from game.core.account import ExternalIdentity, IdentityEvidence  # noqa: E402
from game.core.gameplay import PartyState  # noqa: E402
from game.core.persistence import PARTY_AGGREGATE  # noqa: E402
from game.features.party.service import PARTY_SCOPE_ID  # noqa: E402
from game.features.party_battle import PARTY_BATTLE_CHALLENGE_AGGREGATE  # noqa: E402
from game.features.party_battle.models import PartyBattleChallengeState  # noqa: E402


def main() -> None:
    with TemporaryDirectory() as directory:
        services = build_game_services(
            database_path=Path(directory) / "party-battle.db",
            identity_secret="party-battle-feature-secret",
        )
        services.database.initialize()
        characters = tuple(_create_character(services, f"party-battle-{index}", f"队员{index}") for index in range(3))
        now = _now()
        first = services.party.create("party-battle-create", characters[0].id, logical_time=now)
        assert first.status == "created" and first.party is not None
        party = first.party
        for index, character in enumerate(characters[1:], start=1):
            invited = services.party.invite(
                f"party-battle-invite-{index}",
                characters[0].id,
                character.id,
                logical_time=now,
            )
            assert invited.request is not None
            accepted = services.party.accept(
                f"party-battle-accept-{index}",
                character.id,
                invited.request.id,
                logical_time=now,
            )
            assert accepted.status == "accepted" and accepted.party is not None
            party = accepted.party
        selected = services.party_battles.select(
            "party-battle-select",
            party.id,
            characters[0].id,
            1,
            logical_time=now,
        )
        assert selected.status == "selected" and selected.challenge is not None
        moved = services.party.set_slot(
            "party-battle-move-slot",
            characters[0].id,
            characters[1].id,
            2,
            logical_time=now,
        )
        assert moved.party is not None
        stale = services.party_battles.set_ready(
            "party-battle-stale-ready",
            party.id,
            characters[0].id,
            True,
            logical_time=now,
        )
        assert stale.status == "party_changed"
        restored = services.party.set_slot(
            "party-battle-restore-slot",
            characters[0].id,
            characters[1].id,
            1,
            logical_time=now,
        )
        assert restored.party is not None
        for index, character in enumerate(characters):
            prepared = services.party_battles.set_ready(
                f"party-battle-ready-{index}",
                party.id,
                character.id,
                True,
                logical_time=now,
            )
            assert prepared.status == "ready"
        with services.database.unit_of_work(write=False) as uow:
            prepared_party_state = services.party_battles.snapshots.require(
                uow,
                PARTY_AGGREGATE,
                PARTY_SCOPE_ID,
                PartyState,
            )
        assert all(
            value.ready
            for value in prepared_party_state.parties[party.id].members.values()
        )
        result = services.party_battles.challenge(
            "party-battle-start",
            party.id,
            characters[0].id,
            logical_time=now,
        )
        assert result.status in {"victory", "draw", "defeated"}
        assert result.report_id and result.share_id
        replayed = services.party_battles.challenge(
            "party-battle-start",
            party.id,
            characters[0].id,
            logical_time=now,
        )
        assert replayed.status == "replayed"
        assert replayed.report_id == result.report_id
        with services.database.unit_of_work(write=False) as uow:
            challenge = services.party_battles.snapshots.require(
                uow,
                PARTY_BATTLE_CHALLENGE_AGGREGATE,
                party.id,
                PartyBattleChallengeState,
            )
            party_state = services.party_battles.snapshots.require(
                uow,
                PARTY_AGGREGATE,
                PARTY_SCOPE_ID,
                PartyState,
            )
        assert challenge.attempt_count == 1
        assert not any(value.ready for value in party_state.parties[party.id].members.values())
        assert services.battle_reports.reference(result.report_id) is not None
    print("party battle feature tests passed")


def _create_character(services, subject: str, name: str):
    evidence = IdentityEvidence(
        f"evidence:{subject}",
        ExternalIdentity("platform.local", "party-battle", "identity.user", "private", subject),
        (),
        "message.local",
        _now(),
    )
    result = services.create_character(evidence, requested_name=name)
    assert result.status == "created" and result.receipt is not None
    return result.receipt.character


def _now():
    from datetime import datetime, timezone

    return datetime(2026, 7, 20, 13, 0, tzinfo=timezone.utc)


if __name__ == "__main__":
    main()
