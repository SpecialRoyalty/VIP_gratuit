"""Adresse de parrainage indépendante de l'invitation Telegram du groupe."""
from html import escape
from secrets import token_urlsafe

from sqlalchemy import select
from telegram.helpers import create_deep_linked_url

from .db import SessionLocal
from .models import Campaign, CampaignReferral

REFERRAL_PREFIX = 'ref_'


def share_address(bot, token: str) -> str:
    return create_deep_linked_url(bot.username, REFERRAL_PREFIX + token)


def clickable_url(url: str) -> str:
    safe = escape(url)
    return f'<a href="{safe}">{safe}</a>'


async def share_url(bot, campaign_id: int) -> str:
    async with SessionLocal() as db:
        referral = await db.get(CampaignReferral, campaign_id)
        if referral is None:
            # Sérialise le premier affichage du lien pour cette campagne.
            await db.scalar(select(Campaign.id).where(Campaign.id == campaign_id).with_for_update())
            referral = await db.get(CampaignReferral, campaign_id)
            if referral is None:
                referral = CampaignReferral(campaign_id=campaign_id, token=token_urlsafe(24))
                db.add(referral)
                await db.commit()
        return share_address(bot, referral.token)
