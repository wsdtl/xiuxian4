"""全服活动开放注册接口与只读筛选目录。"""

from __future__ import annotations

from datetime import datetime, timedelta

from game.content.catalog.activity import (
    GLOBAL_ACTIVITY_CLOSING_WINDOW,
    GLOBAL_ACTIVITY_OPENING_WINDOW,
    GLOBAL_ACTIVITY_SPOTLIGHT_LIMIT,
)
from game.core.gameplay import (
    ActivityCatalog,
    ActivityState,
    ActivityStatus,
    SkinProjector,
    character_name_display_width,
)

from .models import (
    ActivitySpotlightPolicy,
    GLOBAL_ACTIVITY_SCOPE_ID,
    GlobalActivityRegistration,
    GlobalActivityPresentation,
    GlobalActivitySelection,
    GlobalActivityView,
)


class GlobalActivityCatalog:
    """组件可扩展、回复层只读取的全服活动注册目录。"""

    def __init__(self) -> None:
        self._registrations: dict[str, GlobalActivityRegistration] = {}

    def register(
        self,
        registration: GlobalActivityRegistration,
    ) -> GlobalActivityRegistration:
        previous = self._registrations.get(registration.definition_id)
        if previous is not None:
            if previous == registration:
                return previous
            raise ValueError(f"全服活动重复注册: {registration.definition_id}")
        self._registrations[registration.definition_id] = registration
        return registration

    def registrations(self) -> tuple[GlobalActivityRegistration, ...]:
        return tuple(
            self._registrations[key]
            for key in sorted(self._registrations)
        )

    def validate(
        self,
        activities: ActivityCatalog,
        projector: SkinProjector,
    ) -> None:
        """注册定义必须存在，并为顶部通栏提供最多四个汉字的短名。"""

        for registration in self.registrations():
            activities.require(registration.definition_id)
            if registration.presentation is None:
                entry = projector.entry(registration.definition_id)
                if not entry.compact_name:
                    raise ValueError(
                        f"全服活动缺少 compact_name: {registration.definition_id}"
                    )
            presentation = resolve_global_activity_presentation(
                registration,
                projector,
            )
            if character_name_display_width(presentation.compact_name) > 8:
                raise ValueError(
                    f"全服活动短名显示宽度超过 8: {presentation.compact_name}"
                )

    def active(
        self,
        state: ActivityState | None,
        *,
        logical_time: datetime,
    ) -> tuple[GlobalActivityView, ...]:
        _aware(logical_time)
        if state is None:
            return ()
        if state.scope_id != GLOBAL_ACTIVITY_SCOPE_ID:
            raise ValueError("全服活动查询使用了错误作用域")
        values = []
        for instance in state.instances.values():
            registration = self._registrations.get(instance.definition_id)
            if registration is None:
                continue
            if (
                instance.status is ActivityStatus.OPEN
                and instance.opens_at <= logical_time < instance.closes_at
            ):
                values.append(GlobalActivityView(instance, registration))
        return tuple(sorted(values, key=_sort_key))

    def spotlight(
        self,
        state: ActivityState | None,
        *,
        logical_time: datetime,
        limit: int = GLOBAL_ACTIVITY_SPOTLIGHT_LIMIT,
    ) -> GlobalActivitySelection:
        if limit < 1:
            raise ValueError("活动通栏展示数量必须大于 0")
        visible = tuple(
            view
            for view in self.active(state, logical_time=logical_time)
            if view.registration.spotlight.visible(view.instance, logical_time)
        )
        return GlobalActivitySelection(
            visible[:limit],
            max(0, len(visible) - limit),
        )

    def find_active(
        self,
        state: ActivityState | None,
        instance_id: object,
        *,
        logical_time: datetime,
    ) -> GlobalActivityView | None:
        normalized_id = str(instance_id or "").strip()
        return next(
            (
                view
                for view in self.active(state, logical_time=logical_time)
                if view.instance.id == normalized_id
            ),
            None,
        )


def register_global_activity(
    definition_id: object,
    *,
    priority: int = 0,
    opening_window: timedelta = GLOBAL_ACTIVITY_OPENING_WINDOW,
    closing_window: timedelta = GLOBAL_ACTIVITY_CLOSING_WINDOW,
    entry_intent_id: object | None = None,
    presentation: GlobalActivityPresentation | None = None,
) -> GlobalActivityRegistration:
    """供具体活动组件声明全服活动，无需修改活动通栏。"""

    return global_activity_catalog.register(
        GlobalActivityRegistration(
            definition_id,
            priority,
            ActivitySpotlightPolicy(opening_window, closing_window),
            entry_intent_id,
            presentation,
        )
    )


def resolve_global_activity_presentation(
    registration: GlobalActivityRegistration,
    projector: SkinProjector,
) -> GlobalActivityPresentation:
    """固定活动直接返回自身展示，普通活动继续使用当前世界皮肤。"""

    if registration.presentation is not None:
        return registration.presentation
    entry = projector.entry(registration.definition_id)
    return GlobalActivityPresentation(
        projector.name(registration.definition_id),
        projector.compact_name(registration.definition_id),
        entry.description,
    )


def _sort_key(view: GlobalActivityView) -> tuple[object, ...]:
    instance = view.instance
    return (
        -view.registration.priority,
        instance.closes_at,
        instance.opens_at,
        instance.id,
    )


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("全服活动查询时间必须包含时区")


global_activity_catalog = GlobalActivityCatalog()


__all__ = [
    "GlobalActivityCatalog",
    "global_activity_catalog",
    "register_global_activity",
    "resolve_global_activity_presentation",
]
