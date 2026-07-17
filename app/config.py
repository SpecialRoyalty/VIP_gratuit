from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _int_list(value: str) -> tuple[int, ...]:
    return tuple(int(x.strip()) for x in value.split(',') if x.strip())


@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_ids: tuple[int, ...]
    database_url: str
    leakimedia_url: str
    invite_goal: int
    vip_days_per_goal: int
    vip_link_ttl_hours: int
    join_validation_minutes: int
    stagnation_hours: int
    reminder_days: tuple[int, ...]


def load_settings() -> Settings:
    token = os.getenv('BOT_TOKEN', '').strip()
    db = os.getenv('DATABASE_URL', '').strip()
    owners = _int_list(os.getenv('OWNER_IDS', ''))
    if not token:
        raise RuntimeError('BOT_TOKEN manquant')
    if not db:
        raise RuntimeError('DATABASE_URL manquant')
    if not owners:
        raise RuntimeError('OWNER_IDS doit contenir au moins un ID Telegram')
    if db.startswith('postgres://'):
        db = db.replace('postgres://', 'postgresql+asyncpg://', 1)
    elif db.startswith('postgresql://') and '+asyncpg' not in db:
        db = db.replace('postgresql://', 'postgresql+asyncpg://', 1)
    return Settings(
        bot_token=token,
        owner_ids=owners,
        database_url=db,
        leakimedia_url=os.getenv('LEAKIMEDIA_URL', 'https://leakimedia.com/'),
        invite_goal=int(os.getenv('INVITE_GOAL', '100')),
        vip_days_per_goal=int(os.getenv('VIP_DAYS_PER_GOAL', '10')),
        vip_link_ttl_hours=int(os.getenv('VIP_LINK_TTL_HOURS', '24')),
        join_validation_minutes=int(os.getenv('JOIN_VALIDATION_MINUTES', '5')),
        stagnation_hours=int(os.getenv('STAGNATION_HOURS', '72')),
        reminder_days=_int_list(os.getenv('REMINDER_DAYS', '5,3,1')),
    )


settings = load_settings()
