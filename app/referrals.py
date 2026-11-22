"""Création, contrôle et réparation des invitations directes au groupe PUB."""
from dataclasses import dataclass
from datetime import timedelta
from html import escape

from sqlalchemy import select
from telegram import ChatInviteLink
from telegram.error import BadRequest, RetryAfter, TelegramError

from .db import SessionLocal
from .models import Campaign, CampaignInviteLink, CampaignStatus, EventType, Group, GroupRole, MetricEvent, User
from .services import now

# Les adresses émises en V6.1/V6.2 restent résolubles par le bot.
LEGACY_PREFIX = 'ref_'
_INVALID_LINK_ERRORS = {
    'invite_hash_expired', 'invite_hash_invalid', 'invite link expired',
    'invite link is expired', 'invite link not found', 'invite link is invalid',
    'invite link is revoked', 'wrong invite link', 'invite link invalid',
}
_retry_at = None


@dataclass(frozen=True)
class LinkCheck:
    link: str | None = None
    reason: str | None = None
    replaced: bool = False
    throttled: bool = False


def clickable_url(url: str) -> str:
    safe = escape(url)
    return f'<a href="{safe}">{safe}</a>'


def _link_problem(link: ChatInviteLink) -> str | None:
    if link.is_revoked:
        return 'Lien révoqué par Telegram.'
    if link.expire_date or link.member_limit or link.creates_join_request:
        return ('Telegram a renvoyé un lien avec des restrictions '
                f'(expiration={link.expire_date}, limite={link.member_limit}, '
                f'demande d’adhésion={link.creates_join_request}).')
    return None


def _link_name(user_id: int) -> str:
    return f'parrain-{user_id}'[:32]


async def _create_link(bot, group_id: int, user_id: int) -> str:
    # Les paramètres facultatifs sont omis. La réponse Telegram est vérifiée.
    link = await bot.create_chat_invite_link(chat_id=group_id, name=_link_name(user_id))
    problem = _link_problem(link)
    if problem:
        try:
            if not link.is_revoked:
                await bot.revoke_chat_invite_link(group_id, link.invite_link)
        except TelegramError:
            pass
        raise TelegramError(problem)
    return link.invite_link


async def start_campaign(bot, group: Group, user_id: int) -> Campaign:
    async with SessionLocal() as db:
        await db.scalar(select(User.telegram_id).where(User.telegram_id == user_id).with_for_update())
        campaign = await db.scalar(select(Campaign).where(
            Campaign.user_id == user_id, Campaign.status == CampaignStatus.active,
        ).order_by(Campaign.id.desc()).limit(1))
        if campaign:
            return campaign

        link = await _create_link(bot, group.chat_id, user_id)
        campaign = Campaign(user_id=user_id, pub_group_id=group.chat_id,
                            vip_group_id=group.vip_group_id, invite_link=link)
        db.add(campaign)
        await db.flush()
        db.add(CampaignInviteLink(campaign_id=campaign.id, invite_link=link, last_checked_at=now()))
        db.add(MetricEvent(event_type=EventType.campaign_started, pub_group_id=group.chat_id,
                           ad_version=group.ad_version, user_id=user_id))
        await db.commit()
        return campaign


async def check_campaign_link(bot, campaign_id: int, *, replace_broken: bool) -> LinkCheck:
    """Normalise le lien existant. Un remplacement exige une demande et un défaut confirmé."""
    global _retry_at
    if _retry_at and now() < _retry_at:
        return LinkCheck(reason='Limite Telegram atteinte.', throttled=True)

    async with SessionLocal() as db:
        campaign = await db.scalar(select(Campaign).where(
            Campaign.id == campaign_id, Campaign.status == CampaignStatus.active,
        ).with_for_update())
        if not campaign:
            return LinkCheck(reason='Campagne inactive.')
        group = await db.get(Group, campaign.pub_group_id)
        if not group or group.role != GroupRole.pub:
            return LinkCheck(reason='Groupe partenaire indisponible.')

        current = campaign.invite_link
        reason = None
        unavailable = False
        replaceable = False
        replacement = None
        throttled = False
        try:
            try:
                link = await bot.edit_chat_invite_link(
                    chat_id=campaign.pub_group_id, invite_link=current, name=_link_name(campaign.user_id),
                )
            except BadRequest as exc:
                if str(exc).casefold() not in _INVALID_LINK_ERRORS:
                    raise
                reason = str(exc)
                unavailable = replaceable = True
            else:
                if link.invite_link != current:
                    reason = 'Telegram a retourné une URL différente du lien contrôlé.'
                else:
                    reason = _link_problem(link)
                    unavailable = link.is_revoked
                    replaceable = reason is not None
            if replaceable and replace_broken:
                replacement = await _create_link(bot, campaign.pub_group_id, campaign.user_id)
        except RetryAfter as exc:
            delay = exc.retry_after
            if not isinstance(delay, timedelta):
                delay = timedelta(seconds=float(delay))
            _retry_at = now() + delay
            reason = 'Limite Telegram atteinte.'
            throttled = True
        except TelegramError as exc:
            reason = f'{type(exc).__name__}: {exc}'

        history = await db.scalar(select(CampaignInviteLink).where(CampaignInviteLink.invite_link == current))
        if history is None:
            history = CampaignInviteLink(campaign_id=campaign.id, invite_link=current, created_at=campaign.created_at)
            db.add(history)
        history.last_checked_at = now()
        history.last_error = reason
        if replacement:
            history.is_current = False
            history.revoked = unavailable
            history.replaced_at = now()
            campaign.invite_link = replacement
            db.add(CampaignInviteLink(campaign_id=campaign.id, invite_link=replacement, last_checked_at=now()))
        elif reason is None:
            history.revoked = False
        await db.commit()
        if replacement:
            return LinkCheck(link=replacement, replaced=True)
        return LinkCheck(link=current if reason is None else None, reason=reason, throttled=throttled)
