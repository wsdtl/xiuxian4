"""正式业务能力台账；只登记已经落地并可验收的 feature。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BusinessFeaturePlan:
    id: str
    package: str
    responsibility: str
    command_packages: tuple[str, ...] = ()
    scheduled_jobs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.isascii() or not self.id.strip():
            raise ValueError("业务 ID 必须是非空 ASCII 标识")
        if not self.package.isascii() or not self.package.strip():
            raise ValueError("业务包名必须是非空 ASCII 标识")
        if not self.responsibility.strip():
            raise ValueError("业务必须声明单一主要职责")
        if len(set(self.command_packages)) != len(self.command_packages):
            raise ValueError(f"业务 {self.id} 重复登记命令组件")
        if len(set(self.scheduled_jobs)) != len(self.scheduled_jobs):
            raise ValueError(f"业务 {self.id} 重复登记定时任务")


ACTIVE_BUSINESS_FEATURES = (
    BusinessFeaturePlan(
        "battle_report",
        "battle_report",
        "保存、公开读取和清理跨战斗模式共用的战报",
        ("战报",),
        ("game_battle_report_cleanup",),
    ),
    BusinessFeaturePlan(
        "companion",
        "companion",
        "协调伙伴秘境、捕获、名册容量、配装独占与放生",
        ("伙伴",),
    ),
    BusinessFeaturePlan(
        "dimension_shift",
        "dimension_shift",
        "原子扣除跃迁凭证并切换角色世界投影",
        ("跃迁",),
    ),
    BusinessFeaturePlan(
        "dimensional_disaster",
        "dimensional_disaster",
        "协调全服灾厄战斗、贡献、周期和唯一遗羽结算",
        ("多次元灾厄",),
        ("game_dimensional_disaster_maintenance",),
    ),
    BusinessFeaturePlan(
        "draw",
        "draw",
        "扣除抽奖签、推进保底并原子发放奖项",
        ("抽奖",),
    ),
    BusinessFeaturePlan(
        "economy",
        "economy",
        "统一回收、二手交易、估价与中央税金结算",
        ("回收", "二手"),
        ("game_market_expiration",),
    ),
    BusinessFeaturePlan(
        "exploration",
        "exploration",
        "协调持续探险、战斗、掉落与奖励联合结算",
        ("探险",),
        ("game_exploration_settlement",),
    ),
    BusinessFeaturePlan(
        "lottery",
        "lottery",
        "处理单期购票、环形开奖、退票与中奖入账",
        ("彩票",),
        ("game_lottery_draw",),
    ),
    BusinessFeaturePlan(
        "player",
        "player",
        "提供账号到角色入口、角色总览、个人设置、提醒和活动读模型",
        ("角色", "提醒", "活动"),
    ),
    BusinessFeaturePlan(
        "rest",
        "rest",
        "协调主行动占用、离线恢复和主动结束休息",
        ("休息",),
        ("game_rest_settlement",),
    ),
    BusinessFeaturePlan(
        "sparring",
        "sparring",
        "协调切磋邀请、双方真实配装战斗和公开战报",
        ("切磋",),
    ),
    BusinessFeaturePlan(
        "special_items",
        "special_items",
        "原子提交需要长期状态的特殊物品效果",
        ("物品",),
    ),
)


def business_feature(feature_id: str) -> BusinessFeaturePlan:
    key = str(feature_id or "").strip()
    try:
        return next(value for value in ACTIVE_BUSINESS_FEATURES if value.id == key)
    except StopIteration as exc:
        raise KeyError(f"未知正式业务：{key}") from exc


__all__ = ["ACTIVE_BUSINESS_FEATURES", "BusinessFeaturePlan", "business_feature"]
