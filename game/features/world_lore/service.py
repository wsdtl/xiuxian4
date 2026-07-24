"""世界志解锁读取与成功展示后的已读确认。"""

from __future__ import annotations

from dataclasses import replace

from game.content.world_lore import WorldLoreCatalog
from game.core.gameplay import StableId, stable_id

from .models import (
    WORLD_LORE_AGGREGATE,
    WorldLoreAcknowledgeResult,
    WorldLoreState,
    WorldLoreView,
    world_lore_state_id,
)


class WorldLoreFeature:
    """读取行纪投影决定世界志可见性，只写本业务的已读状态。"""

    def __init__(
        self,
        database,
        lore: WorldLoreCatalog,
        snapshots,
        progress_reader,
        playable_world_ids: tuple[StableId, ...],
    ) -> None:
        expected = tuple(stable_id(value, field="world id") for value in playable_world_ids)
        if lore.world_ids() != expected:
            raise ValueError("正式世界志与可进入世界的顺序或范围不一致")
        self.database = database
        self.lore = lore
        self.snapshots = snapshots
        self.progress_reader = progress_reader

    def view(
        self,
        character_id: str,
        world_id: StableId,
        *,
        current_world_id: StableId,
    ) -> WorldLoreView:
        actor = str(character_id or "").strip()
        if not actor:
            raise ValueError("世界志查询缺少角色 ID")
        world = stable_id(world_id, field="world id")
        current_world = stable_id(current_world_id, field="current world id")
        definition = self.lore.require(world)
        progress = self.progress_reader(actor, world)
        with self.database.unit_of_work(write=False) as uow:
            state = self.snapshots.load(
                uow,
                WORLD_LORE_AGGREGATE,
                world_lore_state_id(actor, world),
                WorldLoreState,
            )
        available = world == current_world or progress.points > 0 or state is not None
        percent = progress.percent if available else 0
        unlocked = definition.unlocked(percent) if available else ()
        return WorldLoreView(
            actor,
            definition,
            percent,
            available,
            unlocked,
            state.seen_record_ids if state is not None else (),
        )

    def acknowledge(
        self,
        character_id: str,
        world_id: StableId,
        record_ids: tuple[StableId, ...],
        *,
        current_world_id: StableId,
        logical_time,
    ) -> WorldLoreAcknowledgeResult:
        if logical_time.tzinfo is None or logical_time.utcoffset() is None:
            raise ValueError("世界志确认时间必须包含时区")
        view = self.view(
            character_id,
            world_id,
            current_world_id=current_world_id,
        )
        if not view.available:
            raise ValueError("尚未在这个世界留下可阅读的行纪")
        requested = tuple(
            stable_id(value, field="world lore record id")
            for value in record_ids
        )
        if len(requested) != len(set(requested)):
            raise ValueError("世界志确认包含重复记录")
        unlocked_ids = {value.id for value in view.unlocked_records}
        if not set(requested).issubset(unlocked_ids):
            raise ValueError("不能确认尚未解锁的世界志记录")

        aggregate_id = world_lore_state_id(character_id, world_id)
        with self.database.unit_of_work() as uow:
            previous = self.snapshots.load(
                uow,
                WORLD_LORE_AGGREGATE,
                aggregate_id,
                WorldLoreState,
            )
            if previous is None:
                state = WorldLoreState(
                    str(character_id).strip(),
                    world_id,
                    requested,
                )
                self.snapshots.insert(
                    uow,
                    WORLD_LORE_AGGREGATE,
                    aggregate_id,
                    state,
                    logical_time,
                )
                uow.commit()
                return WorldLoreAcknowledgeResult("acknowledged", state)

            newly_seen = tuple(
                value for value in requested if value not in previous.seen_record_ids
            )
            combined = (*previous.seen_record_ids, *newly_seen)
            if combined == previous.seen_record_ids:
                return WorldLoreAcknowledgeResult("already_seen", previous)
            state = replace(
                previous,
                seen_record_ids=combined,
                revision=previous.revision + 1,
            )
            self.snapshots.update(
                uow,
                WORLD_LORE_AGGREGATE,
                aggregate_id,
                previous,
                state,
                logical_time,
            )
            uow.commit()
            return WorldLoreAcknowledgeResult("acknowledged", state)


__all__ = ["WorldLoreFeature"]
