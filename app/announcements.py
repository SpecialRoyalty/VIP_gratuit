"""Annonce de mise à jour, une fois pour les utilisateurs présents au déploiement."""
from __future__ import annotations
import asyncio
from datetime import timedelta
from html import escape

from sqlalchemy import exists, func, insert, literal, select
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError

from .db import SessionLocal
from .models import ReleaseNotice, ReleaseNoticeDelivery, User
from .services import active_campaign, now
from .challenges import keyboard

NOTICE_KEY = 'stable-links-and-ranks-v6'
_notice_lock = asyncio.Lock()


async def prepare_notice():
    async with SessionLocal() as db:
        notice = await db.get(ReleaseNotice, NOTICE_KEY)
        if not notice:
            notice = ReleaseNotice(key=NOTICE_KEY, audience_cutoff=now())
            db.add(notice)
            await db.flush()
        missing = ~exists(select(ReleaseNoticeDelivery.id).where(
            ReleaseNoticeDelivery.notice_key == NOTICE_KEY,
            ReleaseNoticeDelivery.user_id == User.telegram_id,
        ))
        await db.execute(insert(ReleaseNoticeDelivery).from_select(
            ['notice_key', 'user_id', 'status', 'next_attempt_at'],
            select(literal(NOTICE_KEY), User.telegram_id, literal('pending'), literal(now())).where(
                User.created_at <= notice.audience_cutoff, missing,
            ),
        ))
        # Si le processus s'est arrêté après l'envoi mais avant sa confirmation,
        # ne pas renvoyer automatiquement et risquer de contacter deux fois.
        sending = list((await db.scalars(select(ReleaseNoticeDelivery).where(
            ReleaseNoticeDelivery.notice_key == NOTICE_KEY, ReleaseNoticeDelivery.status == 'sending'
        ))).all())
        for row in sending:
            row.status = 'uncertain'
            row.last_error = 'Processus interrompu pendant un envoi ; pas de renvoi automatique.'
        await db.commit()


async def deliver_notice_batch(context):
    async with _notice_lock:
        async with SessionLocal() as db:
            ids = list((await db.scalars(select(ReleaseNoticeDelivery.id).where(
                ReleaseNoticeDelivery.notice_key == NOTICE_KEY,
                ReleaseNoticeDelivery.status == 'pending',
                ReleaseNoticeDelivery.next_attempt_at <= now(),
            ).order_by(ReleaseNoticeDelivery.id).limit(25))).all())
        for delivery_id in ids:
            async with SessionLocal() as db:
                delivery = await db.scalar(select(ReleaseNoticeDelivery).where(
                    ReleaseNoticeDelivery.id == delivery_id).with_for_update())
                if delivery.status != 'pending':
                    continue
                delivery.status = 'sending'
                await db.commit()
                uid = delivery.user_id
            camp = await active_campaign(uid)
            text = ('🔗 <b>Ton lien de parrainage devient stable</b>\n\n'
                    'Les renouvellements automatiques sont supprimés. '
                    'Les liens de parrainage sont sans expiration ni limite d’invités.\n'
                    'Tes minutes et tes invitations sont conservées.\n\n')
            if camp:
                text += f'Voici ton lien actuel à conserver :\n<code>{escape(camp.invite_link)}</code>\n\n'
            else:
                text += 'Pour reprendre, ouvre « VIP GRATUIT » depuis un groupe partenaire et obtiens ton lien personnel.\n\n'
            text += ('🏅 De nouveaux rangs récompensent tes invitations : Bronze, Silver, Gold, Platine et Omega.\n'
                     '🏆 Un défi VIP à vie est disponible, uniquement si tu choisis d’y participer.\n\n'
                     'Un groupe supprimé ou une révocation manuelle peut toujours rendre un lien inutilisable.')
            status, error, retry_at = 'sent', None, None
            try:
                await context.bot.send_message(uid, text, parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard([[('📊 MON ESPACE', 'u:counter')], [('🏅 LES RANGS', 'u:ranks')]]))
            except RetryAfter as exc:
                status, error = 'pending', f'{type(exc).__name__}: {exc}'
                delay = exc.retry_after
                if not isinstance(delay, timedelta): delay = timedelta(seconds=float(delay))
                retry_at = now() + delay + timedelta(seconds=1)
            except (Forbidden, BadRequest) as exc:
                status, error = 'failed', f'{type(exc).__name__}: {exc}'
            except TelegramError as exc:
                # Une erreur réseau peut survenir après remise du message.
                status, error = 'uncertain', f'{type(exc).__name__}: {exc}'
            async with SessionLocal() as db:
                row = await db.get(ReleaseNoticeDelivery, delivery_id)
                row.status, row.last_error = status, error
                if status == 'sent': row.sent_at = now()
                if retry_at:
                    # Respecter le délai pour toute la file, pas seulement ce destinataire.
                    pending = list((await db.scalars(select(ReleaseNoticeDelivery).where(
                        ReleaseNoticeDelivery.notice_key == NOTICE_KEY,
                        ReleaseNoticeDelivery.status == 'pending',
                    ))).all())
                    for pending_row in pending: pending_row.next_attempt_at = retry_at
                await db.commit()
            if retry_at:
                break
            await asyncio.sleep(0.05)


async def show_notice_status(message):
    async with SessionLocal() as db:
        rows = (await db.execute(select(ReleaseNoticeDelivery.status, func.count()).where(
            ReleaseNoticeDelivery.notice_key == NOTICE_KEY,
        ).group_by(ReleaseNoticeDelivery.status))).all()
    counts = dict(rows)
    await message.reply_text(
        '📣 Annonce unique de la mise à jour\n\n'
        f'Envoyées : {counts.get("sent", 0)}\n'
        f'En attente : {counts.get("pending", 0)}\n'
        f'En cours : {counts.get("sending", 0)}\n'
        f'Échecs définitifs : {counts.get("failed", 0)}\n'
        f'Remise incertaine : {counts.get("uncertain", 0)}\n\n'
        'Les envois incertains ne sont pas retentés automatiquement afin d’éviter les doublons.',
        reply_markup=keyboard([[('⬅️ MENU ADMIN', 'a:menu')]]),
    )
