from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from telegram import ChatMember
from telegram.error import TelegramError

from .config import settings
from .db import SessionLocal
from .models import Admin, Campaign, EventType, ForbiddenWord, Group, MetricEvent, User, VipSession, VipSessionStatus

UTC = timezone.utc


def now() -> datetime:
    return datetime.now(UTC)


async def is_admin(user_id: int) -> bool:
    if user_id in settings.owner_ids:
        return True
    async with SessionLocal() as s:
        return bool(await s.scalar(select(Admin.telegram_id).where(Admin.telegram_id == user_id, Admin.active.is_(True))))


async def ensure_user(tg_user) -> User:
    async with SessionLocal() as s:
        row = await s.get(User, tg_user.id)
        if not row:
            row = User(telegram_id=tg_user.id)
            s.add(row)
        row.username = tg_user.username
        row.first_name = tg_user.first_name
        row.last_name = tg_user.last_name
        await s.commit()
        return row


async def active_campaign(user_id: int) -> Campaign | None:
    async with SessionLocal() as s:
        return await s.scalar(select(Campaign).where(Campaign.user_id == user_id, Campaign.status == 'active').order_by(Campaign.id.desc()))


async def active_session(user_id: int) -> VipSession | None:
    async with SessionLocal() as s:
        return await s.scalar(select(VipSession).where(VipSession.user_id == user_id, VipSession.status.in_([VipSessionStatus.link_created, VipSessionStatus.active, VipSessionStatus.kick_pending])).order_by(VipSession.id.desc()))


async def record(event: EventType, pub_group_id: int | None = None, user_id: int | None = None, ad_version: int | None = None, metadata: dict | None = None) -> None:
    async with SessionLocal() as s:
        s.add(MetricEvent(event_type=event, pub_group_id=pub_group_id, user_id=user_id, ad_version=ad_version, metadata_json=json.dumps(metadata or {}, ensure_ascii=False)))
        await s.commit()


async def bot_rights(bot, chat_id: int, require_delete: bool = False) -> tuple[bool, str]:
    try:
        m = await bot.get_chat_member(chat_id, bot.id)
    except TelegramError as exc:
        return False, str(exc)
    if m.status == ChatMember.OWNER:
        return True, 'propriétaire'
    if m.status != ChatMember.ADMINISTRATOR:
        return False, 'le bot n’est pas administrateur'
    if not getattr(m, 'can_invite_users', False):
        return False, 'droit « inviter des utilisateurs » manquant'
    if not getattr(m, 'can_restrict_members', False):
        return False, 'droit « bannir/restreindre » manquant'
    if require_delete and not getattr(m, 'can_delete_messages', False):
        return False, 'droit « supprimer les messages » manquant'
    return True, 'OK'


async def public_group_link(bot, chat) -> str:
    if getattr(chat, 'username', None):
        return f'https://t.me/{chat.username}'
    try:
        rights, _ = await bot_rights(bot, chat.id)
        if rights:
            link = await bot.create_chat_invite_link(chat.id, name='signalement-raccordement', expire_date=now() + timedelta(hours=24), member_limit=1)
            return link.invite_link
    except TelegramError:
        pass
    return f'ID Telegram : <code>{chat.id}</code>'


def normalized_profile(user) -> str:
    return ' '.join(filter(None, [user.first_name, user.last_name, user.username])).casefold()


async def forbidden_match(user) -> str | None:
    text = normalized_profile(user)
    async with SessionLocal() as s:
        words = list((await s.scalars(select(ForbiddenWord).where(ForbiddenWord.active.is_(True)))).all())
    for item in words:
        w = item.word.casefold().strip()
        if not w:
            continue
        if item.exact_word:
            if re.search(rf'(?<!\w){re.escape(w)}(?!\w)', text, flags=re.IGNORECASE):
                return item.word
        elif w in text:
            return item.word
    return None


async def remaining_minutes(campaign: Campaign) -> int:
    return max(0, campaign.minutes_earned - campaign.minutes_consumed)


def token() -> str:
    return secrets.token_urlsafe(12).replace('-', '').replace('_', '')[:16]
