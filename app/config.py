from __future__ import annotations

from dataclasses import dataclass
import os


def _ids(value: str) -> set[int]:
    return {int(x.strip()) for x in value.split(',') if x.strip()}


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.environ.get('BOT_TOKEN', '')
    database_url: str = os.environ.get('DATABASE_URL', '')
    owner_ids: set[int] = frozenset(_ids(os.environ.get('OWNER_IDS', '')))
    validation_minutes: int = int(os.environ.get('JOIN_VALIDATION_MINUTES', '5'))
    minimum_minutes: int = int(os.environ.get('MINIMUM_VIP_MINUTES', '10'))
    vip_link_ttl_minutes: int = int(os.environ.get('VIP_LINK_TTL_MINUTES', '15'))
    trial_minutes: int = int(os.environ.get('TRIAL_MINUTES', '2'))
    kick_retry_seconds: int = int(os.environ.get('KICK_RETRY_SECONDS', '20'))
    health_interval_minutes: int = int(os.environ.get('HEALTH_INTERVAL_MINUTES', '5'))
    group_lost_grace_minutes: int = int(os.environ.get('GROUP_LOST_GRACE_MINUTES', '10'))
    broadcast_delay_seconds: float = float(os.environ.get('BROADCAST_DELAY_SECONDS', '0.05'))
    trend_drop_percent: float = float(os.environ.get('TREND_DROP_PERCENT', '20'))
    timezone: str = os.environ.get('TIMEZONE', 'Europe/Paris')

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append('BOT_TOKEN')
        if not self.database_url:
            missing.append('DATABASE_URL')
        if not self.owner_ids:
            missing.append('OWNER_IDS')
        if missing:
            raise RuntimeError('Variables manquantes : ' + ', '.join(missing))


settings = Settings()
