"""Rangs indépendants de l'inscription au défi VIP à vie."""
from dataclasses import dataclass
from sqlalchemy import func, select
from .models import Campaign


@dataclass(frozen=True)
class Rank:
    name: str
    icon: str
    threshold: int
    minutes: int


RANKS = (
    Rank('Bronze', '🥉', 0, 1),
    Rank('Silver', '🥈', 50, 2),
    Rank('Gold', '🥇', 150, 3),
    Rank('Platine', '💎', 300, 4),
    Rank('Omega', 'Ω', 500, 5),
)


def rank_for(total: int) -> Rank:
    return next(rank for rank in reversed(RANKS) if total >= rank.threshold)


def next_rank(total: int) -> Rank | None:
    return next((rank for rank in RANKS if rank.threshold > total), None)


def progress_bar(value: int, target: int, size: int = 10) -> str:
    filled = min(size, max(0, value) * size // max(1, target))
    return '🟩' * filled + '⬜' * (size - filled)


async def total_valid_invites(db, user_id: int) -> int:
    # Inclut les anciennes campagnes, sans recalculer ni modifier leurs crédits.
    return int(await db.scalar(select(func.coalesce(func.sum(Campaign.valid_invites), 0)).where(
        Campaign.user_id == user_id
    )) or 0)


def rank_summary(total: int) -> str:
    rank = rank_for(total)
    following = next_rank(total)
    text = (f'{rank.icon} <b>Rang {rank.name}</b> — {total} invitations cumulées\n'
            f'🎁 <b>{rank.minutes} minute(s)</b> par nouvelle invitation validée')
    if following:
        text += (f'\n{progress_bar(total-rank.threshold, following.threshold-rank.threshold)}\n'
                 f'Encore {following.threshold-total} invitation(s) pour {following.name}')
    else:
        text += '\n🏅 Rang maximum atteint'
    return text


def rank_rules() -> str:
    return '\n'.join(f'{r.icon} {r.name} : dès {r.threshold} invitations → {r.minutes} min/invitation' for r in RANKS)
