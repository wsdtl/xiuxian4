"""权益资格校验和稳定奖励结算构造。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from ..errors import RuleFailure, RuleOutcome
from ..rewards import RewardSettlement, reward_fingerprint
from .models import (
    GrantCampaign,
    GrantCampaignStatus,
    GrantCredential,
    GrantCredentialStatus,
    GrantEntitlement,
    GrantEntitlementStatus,
    GrantRedemptionCommand,
    GrantRewardBundle,
    GrantUsage,
)


@dataclass(frozen=True)
class GrantAuthorization:
    campaign_id: str
    entitlement_id: str
    account_id: str
    settlement_id: str


class GrantEngine:
    """不读取数据库，只判断一份已加载权益是否可以兑付。"""

    def authorize(
        self,
        campaign: GrantCampaign,
        entitlement: GrantEntitlement,
        usage: GrantUsage,
        command: GrantRedemptionCommand,
        *,
        logical_time: datetime,
        credential: GrantCredential | None = None,
    ) -> RuleOutcome[GrantAuthorization]:
        failure = self._failure(
            campaign,
            entitlement,
            usage,
            command,
            logical_time=logical_time,
            credential=credential,
        )
        if failure is not None:
            return RuleOutcome.failed(failure)
        return RuleOutcome.success(
            GrantAuthorization(
                campaign.id,
                entitlement.id,
                command.account_id,
                grant_settlement_id(entitlement.id),
            )
        )

    @staticmethod
    def build_settlement(
        campaign: GrantCampaign,
        entitlement: GrantEntitlement,
        command: GrantRedemptionCommand,
        bundle: GrantRewardBundle,
    ) -> RewardSettlement:
        reserved = {
            "grant.campaign_id": campaign.id,
            "grant.entitlement_id": entitlement.id,
            "grant.offer_id": str(campaign.offer_id),
            "grant.offer_version": campaign.offer_version,
        }
        conflicts = {
            key for key, value in reserved.items() if key in bundle.metadata and bundle.metadata[key] != value
        }
        if conflicts:
            raise ValueError(f"GrantRewardBundle 覆盖保留元数据：{', '.join(sorted(conflicts))}")
        return RewardSettlement(
            grant_settlement_id(entitlement.id),
            command.account_id,
            command.account_id,
            campaign.source_kind,
            entitlement.id,
            bundle.rewards,
            bundle.expectations,
            {**dict(bundle.metadata), **reserved},
        )

    @staticmethod
    def request_fingerprint(
        command: GrantRedemptionCommand,
        settlement: RewardSettlement,
    ) -> str:
        payload = "\0".join(
            (
                "grant-redemption.v1",
                command.id,
                command.campaign_id,
                command.account_id,
                command.entitlement_id or "",
                reward_fingerprint(settlement),
            )
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _failure(
        campaign: GrantCampaign,
        entitlement: GrantEntitlement,
        usage: GrantUsage,
        command: GrantRedemptionCommand,
        *,
        logical_time: datetime,
        credential: GrantCredential | None,
    ) -> RuleFailure | None:
        if logical_time.tzinfo is None or logical_time.utcoffset() is None:
            raise ValueError("权益兑付逻辑时间必须包含时区")
        if campaign.id != command.campaign_id or entitlement.campaign_id != campaign.id:
            return RuleFailure("grant.campaign_mismatch", "权益不属于指定活动")
        if entitlement.account_id != command.account_id:
            return RuleFailure("grant.account_mismatch", "权益不属于当前账号")
        if entitlement.offer_id != campaign.offer_id or entitlement.offer_version != campaign.offer_version:
            return RuleFailure("grant.offer_mismatch", "权益奖励方案与活动版本不一致")
        if campaign.status is not GrantCampaignStatus.ACTIVE:
            return RuleFailure("grant.campaign_unavailable", "权益活动当前不可领取")
        if logical_time < campaign.starts_at:
            return RuleFailure("grant.campaign_not_started", "权益活动尚未开始")
        if campaign.ends_at is not None and logical_time >= campaign.ends_at:
            return RuleFailure("grant.campaign_expired", "权益活动已经结束")
        if entitlement.status is GrantEntitlementStatus.REVOKED:
            return RuleFailure("grant.entitlement_revoked", "权益已经撤销")
        if entitlement.status is GrantEntitlementStatus.REDEEMED:
            return RuleFailure("grant.entitlement_redeemed", "权益已经兑付")
        if entitlement.expires_at is not None and logical_time >= entitlement.expires_at:
            return RuleFailure("grant.entitlement_expired", "权益已经过期")
        if usage.account_redeemed >= campaign.per_account_limit:
            return RuleFailure("grant.account_limit_reached", "当前账号已达到领取上限")
        if campaign.total_limit is not None and usage.campaign_redeemed >= campaign.total_limit:
            return RuleFailure("grant.campaign_limit_reached", "活动领取额度已经耗尽")
        if credential is None:
            return None
        if credential.campaign_id != campaign.id or entitlement.credential_id != credential.id:
            return RuleFailure("grant.credential_mismatch", "领取凭证与权益不匹配")
        if credential.status is not GrantCredentialStatus.ACTIVE:
            return RuleFailure("grant.credential_revoked", "领取凭证已经撤销")
        if credential.bound_account_id and credential.bound_account_id != command.account_id:
            return RuleFailure("grant.credential_account_mismatch", "领取凭证已绑定其他账号")
        if credential.expires_at is not None and logical_time >= credential.expires_at:
            return RuleFailure("grant.credential_expired", "领取凭证已经过期")
        if credential.usage_limit is not None and usage.credential_used >= credential.usage_limit:
            return RuleFailure("grant.credential_limit_reached", "领取凭证使用次数已经耗尽")
        return None


def grant_settlement_id(entitlement_id: str) -> str:
    value = str(entitlement_id or "").strip()
    if not value:
        raise ValueError("权益 ID 不能为空")
    return f"grant:{sha256(value.encode('utf-8')).hexdigest()[:32]}"


def code_entitlement_id(campaign_id: str, command_id: str, account_id: str) -> str:
    values = tuple(str(value or "").strip() for value in (campaign_id, command_id, account_id))
    if any(not value for value in values):
        raise ValueError("兑换码权益缺少活动、命令或账号身份")
    digest = sha256("\0".join(("grant-code-entitlement.v1", *values)).encode("utf-8")).hexdigest()
    return f"entitlement:{digest[:32]}"
