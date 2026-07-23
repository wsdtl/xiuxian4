"""正式业务能力台账；只登记已经落地并可验收的 feature。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BusinessFeaturePlan:
    id: str
    package: str
    responsibility: str
    command_packages: tuple[str, ...] = ()
    scheduled_jobs: tuple[str, ...] = ()
    # Listed command packages are owned by this feature unless explicitly marked as integrated.
    integrated_command_packages: tuple[str, ...] = ()

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
        if not set(self.integrated_command_packages).issubset(self.command_packages):
            raise ValueError(f"业务 {self.id} 登记了未参与的协作命令组件")


ACTIVE_BUSINESS_FEATURES = (
    BusinessFeaturePlan(
        "covenant_exchange",
        "exchange",
        "原子消费定相尘并按固定目录发放套装图纸",
        ("归航兑换",),
    ),
    BusinessFeaturePlan(
        "equipment_blueprint",
        "equipment_blueprint",
        "原子消费套装图纸并生成仅固定套装身份的随机装备",
        ("物品",),
        integrated_command_packages=("物品",),
    ),
    BusinessFeaturePlan(
        "build_trial",
        "build_trial",
        "读取当前构筑执行固定种子无损战斗，并保存公开战报",
        ("构筑试炼",),
    ),
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
        "协调宠物捕获、人物结交、通用名册、配装独占与告别",
        ("伙伴",),
    ),
    BusinessFeaturePlan(
        "dimension_shift",
        "dimension_shift",
        "原子扣除跃迁凭证、切换真实世界并迁移存在体空间",
        ("跃迁",),
    ),
    BusinessFeaturePlan(
        "world_travel",
        "world_travel",
        "统一校验世界地点意图、主要行动占用与角色位置移动",
        ("地图", "探险", "伙伴"),
        integrated_command_packages=("探险", "伙伴"),
    ),
    BusinessFeaturePlan(
        "breakthrough",
        "breakthrough",
        "原子消费破境凭证、解锁成长关隘、结算经验并恢复角色资源",
        ("突破",),
    ),
    BusinessFeaturePlan(
        "dimensional_disaster",
        "dimensional_disaster",
        "协调全服灾厄战斗、贡献、周期和唯一遗羽结算",
        ("跨界灾厄",),
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
        "world_progress",
        "world_progress",
        "消费探险胜利事实，累计世界区域行纪、发放阶段奖励并维护永久排行",
        ("行纪",),
    ),
    BusinessFeaturePlan(
        "lottery",
        "lottery",
        "处理单期购票、环形开奖、退票与中奖入账",
        ("彩票",),
        ("game_lottery_draw",),
    ),
    BusinessFeaturePlan(
        "party",
        "party",
        "协调三人队伍、社会邀请、成员关系、队长、站位与准备状态",
        ("组队",),
    ),
    BusinessFeaturePlan(
        "party_battle",
        "party_battle",
        "协调跨界组队首领、准备指纹、临时战斗投影、原子奖励与公开战报",
        ("组队",),
        integrated_command_packages=("组队",),
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
