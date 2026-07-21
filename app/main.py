from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from telegram import ChatMember, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import Application, CallbackQueryHandler, ChatMemberHandler, CommandHandler, ContextTypes, MessageHandler, filters

from .config import settings
from .db import SessionLocal, engine, init_db
from .keyboards import admin_menu, broadcast_confirm, choose_vip, group_list, manage_pub, pending_group, start_campaign, user_menu, vip_confirm
from .models import Admin, Campaign, CampaignStatus, EventType, ForbiddenWord, Group, GroupRole, HealthAlert, Invite, InviteStatus, MetricEvent, TrialAccess, TrialStatus, User, VipSession, VipSessionStatus
from .services import active_campaign, active_session, bot_rights, ensure_user, forbidden_match, is_admin, now, public_group_link, record, remaining_minutes, token

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('vip-minutes-bot')


async def notify_admins(bot, text: str, markup=None) -> None:
    async with SessionLocal() as s:
        ids = set(settings.owner_ids) | set((await s.scalars(select(Admin.telegram_id).where(Admin.active.is_(True)))).all())
    for uid in ids:
        try:
            await bot.send_message(uid, text, parse_mode=ParseMode.HTML, reply_markup=markup, disable_web_page_preview=True)
        except TelegramError:
            pass


LOST_CAMPAIGN_MESSAGE = (
    '⚠️ <b>Ta campagne actuelle n’est plus disponible.</b>\n\n'
    'Le groupe associé a été fermé ou n’est plus accessible.\n\n'
    'Tu peux maintenant démarrer une nouvelle campagne depuis un autre groupe partenaire.'
)


def _connection_loss_reason(reason: str) -> bool:
    """Évite de confondre une mauvaise configuration avec un groupe réellement perdu."""
    value = (reason or '').casefold()
    permanent_markers = (
        'chat not found', 'bot is not a member', 'not a member', 'forbidden',
        'kicked', 'banned', 'bot retiré', 'le bot n’est pas administrateur',
    )
    return any(marker in value for marker in permanent_markers)


async def _safe_revoke(bot, chat_id: int, invite_link: str | None) -> bool:
    if not invite_link:
        return False
    try:
        await bot.revoke_chat_invite_link(chat_id, invite_link)
        return True
    except TelegramError:
        return False


async def release_lost_pub_group(bot, group_id: int, reason: str) -> dict[str, int]:
    """Clôture les campagnes mortes et libère leurs utilisateurs, une seule fois.

    Cette opération est idempotente : seules les campagnes encore actives sont traitées.
    Les sessions VIP déjà actives continuent jusqu’à leur expiration normale.
    """
    stats = {'campaigns': 0, 'links': 0, 'invites': 0, 'users': 0}
    async with SessionLocal() as sdb:
        group = await sdb.get(Group, group_id)
        if not group or group.role != GroupRole.pub:
            return stats
        campaigns = list((await sdb.scalars(
            select(Campaign).where(
                Campaign.pub_group_id == group_id,
                Campaign.status == CampaignStatus.active,
            )
        )).all())
        if not campaigns:
            group.authorized = False
            group.role = GroupRole.blocked
            group.last_health_ok = False
            group.health_error = f'groupe perdu : {reason}'
            await sdb.commit()
            return stats

        notifications: list[int] = []
        revoke_campaign_links: list[str] = []
        revoke_trial_links: list[tuple[int, str]] = []
        revoke_vip_links: list[tuple[int, str]] = []

        for camp in campaigns:
            camp.status = CampaignStatus.closed
            camp.pending_invites = 0
            stats['campaigns'] += 1
            notifications.append(camp.user_id)
            revoke_campaign_links.append(camp.invite_link)

            pending = list((await sdb.scalars(select(Invite).where(
                Invite.campaign_id == camp.id, Invite.status == InviteStatus.pending
            ))).all())
            for invite in pending:
                invite.status = InviteStatus.invalid
                invite.validated_at = now()
                invite.reason = 'groupe source perdu'
                stats['invites'] += 1

            trials = list((await sdb.scalars(select(TrialAccess).where(
                TrialAccess.campaign_id == camp.id, TrialAccess.status == TrialStatus.link_created
            ))).all())
            for trial in trials:
                trial.status = TrialStatus.cancelled
                if trial.invite_link:
                    revoke_trial_links.append((trial.vip_group_id, trial.invite_link))

            sessions = list((await sdb.scalars(select(VipSession).where(
                VipSession.campaign_id == camp.id, VipSession.status == VipSessionStatus.link_created
            ))).all())
            for session in sessions:
                session.status = VipSessionStatus.cancelled
                if session.invite_link:
                    revoke_vip_links.append((session.vip_group_id, session.invite_link))

        group.authorized = False
        group.role = GroupRole.blocked
        group.last_health_ok = False
        group.health_error = f'groupe perdu : {reason}'
        await sdb.commit()

    for link in revoke_campaign_links:
        stats['links'] += int(await _safe_revoke(bot, group_id, link))
    for chat_id, link in revoke_trial_links + revoke_vip_links:
        stats['links'] += int(await _safe_revoke(bot, chat_id, link))
    for uid in set(notifications):
        try:
            await bot.send_message(uid, LOST_CAMPAIGN_MESSAGE, parse_mode=ParseMode.HTML)
            stats['users'] += 1
        except TelegramError:
            pass
    return stats


async def reconcile_lost_groups(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Corrige le passé et applique la règle aux groupes désormais perdus."""
    grace = timedelta(minutes=settings.group_lost_grace_minutes)
    totals = {'groups': 0, 'campaigns': 0, 'links': 0, 'invites': 0, 'users': 0}
    async with SessionLocal() as sdb:
        pubs = list((await sdb.scalars(select(Group).where(
            Group.role == GroupRole.pub, Group.authorized.is_(True)
        ))).all())
    for group in pubs:
        ok, reason = await bot_rights(context.bot, group.chat_id)
        if ok:
            continue
        # Un groupe explicitement retiré est confirmé immédiatement. Pour les autres
        # erreurs, on attend le délai afin d’éviter de réagir à une panne passagère.
        explicit = _connection_loss_reason(reason)
        old_enough = group.last_seen_at is None or now() - group.last_seen_at >= grace
        if explicit and old_enough:
            result = await release_lost_pub_group(context.bot, group.chat_id, reason)
            if result['campaigns'] or result['users'] or result['links']:
                totals['groups'] += 1
                for key in ('campaigns', 'links', 'invites', 'users'):
                    totals[key] += result[key]
    context.application.bot_data['last_lost_reconciliation'] = totals
    if totals['groups']:
        await notify_admins(
            context.bot,
            '🧹 <b>Réconciliation des groupes perdus</b>\n\n'
            f'Groupes confirmés perdus : {totals["groups"]}\n'
            f'Campagnes libérées : {totals["campaigns"]}\n'
            f'Liens révoqués : {totals["links"]}\n'
            f'Invitations annulées : {totals["invites"]}\n'
            f'Utilisateurs notifiés : {totals["users"]}'
        )


async def _send_trial_link(message, bot, camp: Campaign, user_id: int) -> bool:
    """Crée ou renvoie l'accès découverte. Retourne True si un lien a été envoyé."""
    async with SessionLocal() as sdb:
        latest = await sdb.scalar(
            select(TrialAccess)
            .where(TrialAccess.user_id == user_id)
            .order_by(TrialAccess.id.desc())
        )
        if latest and latest.status == TrialStatus.link_created:
            if latest.invite_expires_at and latest.invite_expires_at <= now():
                latest.status = TrialStatus.cancelled
                await sdb.commit()
                latest = None
            elif latest.invite_link:
                await message.reply_text(
                    '🎁 <b>Ton accès est prêt.</b>\n\nProfite du VIP 👇',
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton('🚀 ENTRER DANS LE VIP', url=latest.invite_link)]]
                    ),
                )
                return True

        # Un essai déjà commencé/terminé n'est jamais recréé.
        if latest and latest.status in (
            TrialStatus.active,
            TrialStatus.kick_pending,
            TrialStatus.kicked,
        ):
            return False

    ok, reason = await bot_rights(bot, camp.vip_group_id, require_delete=True)
    if not ok:
        await message.reply_text('Le VIP est temporairement indisponible.')
        await notify_admins(bot, f'🚨 <b>VIP indisponible</b>\n{reason}')
        return True

    expiry = now() + timedelta(minutes=settings.vip_link_ttl_minutes)
    try:
        link = await bot.create_chat_invite_link(
            camp.vip_group_id,
            name=f'essai-{user_id}'[:32],
            expire_date=expiry,
            member_limit=1,
        )
    except TelegramError as exc:
        await message.reply_text('Impossible de préparer ton accès pour le moment.')
        await notify_admins(bot, f'🚨 Création du lien découverte impossible : {exc}')
        return True

    async with SessionLocal() as sdb:
        sdb.add(
            TrialAccess(
                campaign_id=camp.id,
                user_id=user_id,
                vip_group_id=camp.vip_group_id,
                invite_link=link.invite_link,
                invite_expires_at=expiry,
            )
        )
        sdb.add(
            MetricEvent(
                event_type=EventType.trial_link,
                pub_group_id=camp.pub_group_id,
                user_id=user_id,
            )
        )
        await sdb.commit()

    await message.reply_text(
        '🎁 <b>Ton accès est prêt.</b>\n\nProfite du VIP 👇',
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('🚀 ENTRER DANS LE VIP', url=link.invite_link)]]
        ),
    )
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or update.effective_chat.type != ChatType.PRIVATE:
        return

    user = await ensure_user(update.effective_user)
    if await is_admin(user.telegram_id) and not context.args:
        await update.message.reply_text(
            '🛠 <b>Panneau administrateur</b>',
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu(),
        )
        return

    if user.banned:
        await update.message.reply_text('⛔ Tu n’as pas invité des personnes FR valides. Tu es banni.')
        return

    camp = await active_campaign(user.telegram_id)

    # Arrivée depuis le bouton « VIP GRATUIT » d'un groupe PUB.
    if context.args and context.args[0].startswith('pub_'):
        source = context.args[0][4:]
        async with SessionLocal() as sdb:
            group = await sdb.scalar(
                select(Group).where(
                    Group.source_token == source,
                    Group.role == GroupRole.pub,
                    Group.authorized.is_(True),
                )
            )
            if group:
                sdb.add(
                    MetricEvent(
                        event_type=EventType.ad_click,
                        pub_group_id=group.chat_id,
                        ad_version=group.ad_version,
                        user_id=user.telegram_id,
                    )
                )
                await sdb.commit()

        if not group or not group.vip_group_id:
            await update.message.reply_text('Cette publicité n’est pas correctement reliée au VIP.')
            return

        # La première origine reste immuable.
        if camp and camp.pub_group_id != group.chat_id:
            if await _send_trial_link(update.effective_message, context.bot, camp, user.telegram_id):
                return
            await show_counter(update.effective_message, user.telegram_id)
            return

        if not camp:
            ok, reason = await bot_rights(context.bot, group.chat_id)
            if not ok:
                await update.message.reply_text('Ce groupe publicitaire est temporairement indisponible.')
                await notify_admins(
                    context.bot,
                    f'🚨 <b>Groupe PUB indisponible</b>\n{group.title}\n{reason}',
                )
                return
            try:
                ref = await context.bot.create_chat_invite_link(
                    group.chat_id,
                    name=f'parrain-{user.telegram_id}'[:32],
                )
            except TelegramError as exc:
                await update.message.reply_text('Impossible de préparer ton accès pour le moment.')
                await notify_admins(
                    context.bot,
                    f'🚨 Création du lien de parrainage impossible pour {group.title}: {exc}',
                )
                return

            async with SessionLocal() as sdb:
                camp = Campaign(
                    user_id=user.telegram_id,
                    pub_group_id=group.chat_id,
                    vip_group_id=group.vip_group_id,
                    invite_link=ref.invite_link,
                )
                sdb.add(camp)
                await sdb.flush()
                sdb.add(
                    MetricEvent(
                        event_type=EventType.campaign_started,
                        pub_group_id=group.chat_id,
                        ad_version=group.ad_version,
                        user_id=user.telegram_id,
                    )
                )
                await sdb.commit()

        if await active_session(user.telegram_id):
            await show_counter(update.effective_message, user.telegram_id)
            return
        if await _send_trial_link(update.effective_message, context.bot, camp, user.telegram_id):
            return
        await show_counter(update.effective_message, user.telegram_id)
        return

    # Correction V3 : une campagne ancienne, créée avant l'ajout de l'essai,
    # reçoit aussi son accès découverte lors d'un simple /start.
    if camp:
        if not await active_session(user.telegram_id):
            if await _send_trial_link(update.effective_message, context.bot, camp, user.telegram_id):
                return
        await show_counter(update.effective_message, user.telegram_id)
        return

    await update.message.reply_text(
        'Ouvre le bouton « 🎁 VIP GRATUIT » depuis un groupe publicitaire pour commencer.'
    )


async def show_counter(message, user_id: int) -> None:
    camp = await active_campaign(user_id)
    if not camp:
        await message.reply_text('Aucune campagne active.')
        return
    rem = await remaining_minutes(camp)
    session = await active_session(user_id)
    status = 'Aucun accès actif'
    if session and session.status == VipSessionStatus.active and session.expires_at:
        seconds = max(0, int((session.expires_at - now()).total_seconds()))
        status = f'VIP actif — environ {seconds // 60} min restantes'
    missing = max(0, settings.minimum_minutes - rem)
    text = (
        '📊 <b>Ton compteur</b>\n\n'
        f'✅ Invitations validées : <b>{camp.valid_invites}</b>\n'
        f'⏳ En vérification : <b>{camp.pending_invites}</b>\n'
        f'❌ Non validées : <b>{camp.invalid_invites}</b>\n\n'
        f'⏱ Crédit disponible : <b>{rem} minute(s)</b>\n'
        f'🔐 Statut : {status}'
    )
    if rem < settings.minimum_minutes:
        text += f'\n\nIl te manque <b>{missing}</b> invitation(s) valide(s) pour générer un accès.'
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=user_menu(rem >= settings.minimum_minutes and not session, missing))


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data or ''
    uid = q.from_user.id

    if data.startswith('a:'):
        if not await is_admin(uid):
            await q.message.reply_text('Accès refusé.')
            return
        await admin_callback(q, context, data)
        return

    if data == 'u:rules':
        await q.message.reply_text(
            '📖 <b>Comment ça marche ?</b>\n\n'
            '1️⃣ Le bot crée un lien vers le groupe PUB depuis lequel tu as commencé.\n'
            '2️⃣ Chaque personne validée ajoute une minute à ton crédit.\n'
            f'3️⃣ À partir de {settings.minimum_minutes} minutes, tu peux générer un lien VIP personnel.\n'
            '4️⃣ Le temps commence seulement lorsque tu rejoins réellement le VIP.\n'
            '5️⃣ Les nouvelles invitations validées pendant ton accès prolongent immédiatement sa durée.\n'
            '6️⃣ À zéro minute, tu es automatiquement retiré du VIP.\n\n'
            'Une seule campagne peut être active à la fois.', parse_mode=ParseMode.HTML)
        return

    if data == 'u:create':
        group_id = context.user_data.get('source_group')
        if not group_id:
            await q.message.reply_text('Reviens depuis le bouton « VIP GRATUIT » du groupe PUB.')
            return
        if await active_campaign(uid):
            await show_counter(q.message, uid); return
        async with SessionLocal() as s:
            user = await s.get(User, uid)
            group = await s.get(Group, group_id)
            if not user or user.banned or not group or not group.vip_group_id:
                await q.message.reply_text('Impossible de démarrer cette campagne.'); return
        ok, reason = await bot_rights(context.bot, group_id)
        if not ok:
            await q.message.reply_text(f'Le groupe PUB n’est pas opérationnel : {reason}.'); return
        try:
            link = await context.bot.create_chat_invite_link(group_id, name=f'parrain-{uid}'[:32])
        except TelegramError as exc:
            await q.message.reply_text(f'Création du lien impossible : {exc}'); return
        async with SessionLocal() as s:
            camp = Campaign(user_id=uid, pub_group_id=group_id, vip_group_id=group.vip_group_id, invite_link=link.invite_link)
            s.add(camp)
            s.add(MetricEvent(event_type=EventType.campaign_started, pub_group_id=group_id, ad_version=group.ad_version, user_id=uid))
            await s.commit()
        await q.message.reply_text(f'✅ <b>Ton lien personnel est prêt !</b>\n\n<code>{link.invite_link}</code>\n\nChaque invitation validée ajoute une minute.', parse_mode=ParseMode.HTML, reply_markup=user_menu(False, settings.minimum_minutes))
        return

    if data in ('u:counter', 'u:link'):
        if data == 'u:link':
            camp = await active_campaign(uid)
            if camp:
                await q.message.reply_text(f'🔗 <b>Ton lien personnel</b>\n\n<code>{camp.invite_link}</code>', parse_mode=ParseMode.HTML)
            else:
                await q.message.reply_text('Aucune campagne active.')
        else:
            await show_counter(q.message, uid)
        return

    if data == 'u:use':
        camp = await active_campaign(uid)
        if not camp:
            await q.message.reply_text('Aucune campagne active.'); return
        rem = await remaining_minutes(camp)
        if rem < settings.minimum_minutes:
            await q.message.reply_text(f'Il faut au moins {settings.minimum_minutes} minutes.'); return
        if await active_session(uid):
            await q.message.reply_text('Tu as déjà un lien ou une session VIP active.'); return
        await q.message.reply_text(f'🔐 Utiliser ton crédit VIP ?\n\nCrédit disponible : <b>{rem} minutes</b>\nLe temps commencera à ton entrée réelle.', parse_mode=ParseMode.HTML, reply_markup=vip_confirm())
        return

    if data == 'u:confirmvip':
        camp = await active_campaign(uid)
        if not camp or await active_session(uid):
            await q.message.reply_text('Accès déjà actif ou campagne absente.'); return
        rem = await remaining_minutes(camp)
        if rem < settings.minimum_minutes:
            await q.message.reply_text('Crédit insuffisant.'); return
        ok, reason = await bot_rights(context.bot, camp.vip_group_id)
        if not ok:
            await q.message.reply_text(f'VIP indisponible : {reason}. Les administrateurs ont été prévenus.')
            await notify_admins(context.bot, f'🚨 <b>VIP indisponible</b>\n{reason}')
            return
        expiry = now() + timedelta(minutes=settings.vip_link_ttl_minutes)
        try:
            link = await context.bot.create_chat_invite_link(camp.vip_group_id, name=f'vip-{uid}'[:32], expire_date=expiry, member_limit=1)
        except TelegramError as exc:
            await q.message.reply_text(f'Impossible de créer le lien VIP : {exc}'); return
        async with SessionLocal() as s:
            session = VipSession(campaign_id=camp.id, user_id=uid, vip_group_id=camp.vip_group_id, invite_link=link.invite_link, invite_expires_at=expiry, allocated_minutes=rem)
            s.add(session)
            s.add(MetricEvent(event_type=EventType.vip_link, pub_group_id=camp.pub_group_id, user_id=uid))
            await s.commit()
        await q.message.reply_text(f'✅ Ton lien VIP personnel est prêt.\n\nIl est valable {settings.vip_link_ttl_minutes} minutes et utilisable une seule fois.', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔐 REJOINDRE LE VIP', url=link.invite_link)]]))
        return


async def admin_callback(q, context, data: str) -> None:
    if data in ('a:menu',):
        await q.message.reply_text('🛠 Panneau administrateur', reply_markup=admin_menu()); return
    if data == 'a:groups':
        async with SessionLocal() as s:
            groups = list((await s.scalars(select(Group).order_by(Group.title))).all())
        await q.message.reply_text('👥 Groupes détectés', reply_markup=group_list(groups)); return
    if data.startswith('a:g:'):
        gid = int(data.split(':')[2])
        async with SessionLocal() as s:
            g = await s.get(Group, gid)
        if not g: return
        if g.role == GroupRole.pub:
            await q.message.reply_text(f'📢 <b>{g.title}</b>\nTexte : {"✅" if g.ad_text else "❌"}\nImage : {"✅" if g.ad_photo_file_id else "❌"}\nVIP associé : {"✅" if g.vip_group_id else "❌"}', parse_mode=ParseMode.HTML, reply_markup=manage_pub(gid))
        elif g.role == GroupRole.pending:
            ok, reason = await bot_rights(context.bot, gid)
            await q.message.reply_text(f'⏳ {g.title}\nDroits : {reason}', reply_markup=pending_group(gid, ok))
        else:
            await q.message.reply_text(f'🔐 VIP : {g.title}')
        return
    if data.startswith('a:check:'):
        gid = int(data.split(':')[2]); ok, reason = await bot_rights(context.bot, gid)
        await q.message.reply_text(f'{"✅" if ok else "❌"} {reason}', reply_markup=pending_group(gid, ok)); return
    if data.startswith('a:role:'):
        _, _, gid_s, role_s = data.split(':'); gid = int(gid_s)
        ok, reason = await bot_rights(context.bot, gid)
        if not ok:
            await q.message.reply_text(f'Configuration impossible : {reason}'); return
        async with SessionLocal() as s:
            g = await s.get(Group, gid); g.role = GroupRole(role_s); g.authorized = True; await s.commit()
        await q.message.reply_text('✅ Rôle enregistré.', reply_markup=admin_menu()); return
    if data.startswith('a:reject:'):
        gid = int(data.split(':')[2])
        try:
            await context.bot.send_message(gid, 'Garde la pêche 👋')
            await context.bot.leave_chat(gid)
        except TelegramError:
            pass
        async with SessionLocal() as s:
            g = await s.get(Group, gid)
            if g: g.role = GroupRole.blocked; g.authorized = False; await s.commit()
        await q.message.reply_text('Groupe refusé et bot débranché.'); return
    if data.startswith('a:adtext:'):
        gid = int(data.split(':')[2]); context.user_data['admin_input'] = ('ad_text', gid)
        await q.message.reply_text('📝 Envoie maintenant le texte publicitaire de ce groupe.'); return
    if data.startswith('a:adphoto:'):
        gid = int(data.split(':')[2]); context.user_data['admin_input'] = ('ad_photo', gid)
        await q.message.reply_text('🖼 Envoie maintenant l’image publicitaire de ce groupe.'); return
    if data.startswith('a:choosevip:'):
        pub_id = int(data.split(':')[2])
        async with SessionLocal() as s:
            vips = list((await s.scalars(select(Group).where(Group.role == GroupRole.vip, Group.authorized.is_(True)))).all())
        await q.message.reply_text('Choisis le VIP associé :', reply_markup=choose_vip(pub_id, vips)); return
    if data.startswith('a:setvip:'):
        _, _, pub_s, vip_s = data.split(':'); pub_id, vip_id = int(pub_s), int(vip_s)
        async with SessionLocal() as s:
            g = await s.get(Group, pub_id); g.vip_group_id = vip_id; await s.commit()
        await q.message.reply_text('✅ VIP associé.'); return
    if data.startswith('a:preview:') or data.startswith('a:publish:'):
        gid = int(data.split(':')[2])
        async with SessionLocal() as s: g = await s.get(Group, gid)
        if not g or not g.ad_text or not g.ad_photo_file_id:
            await q.message.reply_text('Configure d’abord le texte et l’image.'); return
        me = await context.bot.get_me()
        url = f'https://t.me/{me.username}?start=pub_{g.source_token}'
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('🎁 VIP GRATUIT', url=url)]])
        target = q.message.chat_id if data.startswith('a:preview:') else gid
        try:
            await context.bot.send_photo(target, g.ad_photo_file_id, caption=g.ad_text, reply_markup=markup)
            if target == gid:
                await record(EventType.ad_published, pub_group_id=gid, ad_version=g.ad_version)
                await q.message.reply_text('✅ Publicité publiée.')
        except TelegramError as exc:
            await q.message.reply_text(f'Publication impossible : {exc}')
        return
    if data.startswith('a:gstats:'):
        gid = int(data.split(':')[2]); await send_group_stats(q.message, gid); return
    if data == 'a:stats':
        await send_global_stats(q.message); return
    if data == 'a:health':
        await send_health(q.message, context); return
    if data == 'a:broadcast':
        context.user_data['admin_input'] = ('broadcast', 0)
        context.user_data.pop('broadcast_source', None)
        await q.message.reply_text(
            '📣 <b>Broadcast privé</b>\n\nEnvoie maintenant le texte ou la photo à transmettre à tous les utilisateurs du bot.',
            parse_mode=ParseMode.HTML,
        )
        return
    if data == 'a:broadcast:cancel':
        context.user_data.pop('admin_input', None)
        context.user_data.pop('broadcast_source', None)
        await q.message.reply_text('❌ Broadcast annulé.', reply_markup=admin_menu())
        return
    if data == 'a:broadcast:send':
        source = context.user_data.pop('broadcast_source', None)
        context.user_data.pop('admin_input', None)
        if not source:
            await q.message.reply_text('Aucun message à envoyer.')
            return
        await q.message.reply_text('🚀 Broadcast lancé. Le résultat sera envoyé ici à la fin.')
        context.application.create_task(
            run_broadcast(context.bot, q.from_user.id, source[0], source[1]),
            name=f'broadcast-{q.from_user.id}',
        )
        return
    if data == 'a:words':
        async with SessionLocal() as s:
            rows = list((await s.scalars(select(ForbiddenWord).where(ForbiddenWord.active.is_(True)))).all())
        words = '\n'.join(f'• {x.word} ({"mot isolé" if x.exact_word else "contient"})' for x in rows) or 'Aucun mot configuré.'
        context.user_data['admin_input'] = ('forbidden_word', 0)
        await q.message.reply_text('🚫 <b>Mots interdits</b>\n\n' + words + '\n\nEnvoie un nouveau mot pour l’ajouter en mode « mot isolé ».', parse_mode=ParseMode.HTML)


async def admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not await is_admin(update.effective_user.id):
        return
    action = context.user_data.get('admin_input')
    if not action:
        return
    kind, gid = action
    if kind == 'ad_text' and update.message.text:
        async with SessionLocal() as s:
            g = await s.get(Group, gid); g.ad_text = update.message.text; g.ad_version += 1; await s.commit()
        context.user_data.pop('admin_input', None)
        await update.message.reply_text('✅ Texte enregistré.', reply_markup=manage_pub(gid))
    elif kind == 'ad_photo' and update.message.photo:
        async with SessionLocal() as s:
            g = await s.get(Group, gid); g.ad_photo_file_id = update.message.photo[-1].file_id; g.ad_version += 1; await s.commit()
        context.user_data.pop('admin_input', None)
        await update.message.reply_text('✅ Image enregistrée.', reply_markup=manage_pub(gid))
    elif kind == 'broadcast' and (update.message.text or update.message.photo):
        context.user_data['broadcast_source'] = (update.message.chat_id, update.message.message_id)
        async with SessionLocal() as s:
            recipients = int(await s.scalar(select(func.count(User.telegram_id))) or 0)
        await update.message.reply_text('👁 <b>Aperçu du broadcast</b>', parse_mode=ParseMode.HTML)
        await context.bot.copy_message(
            chat_id=update.message.chat_id,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id,
        )
        await update.message.reply_text(
            f'Destinataires enregistrés : <b>{recipients}</b>\n\nConfirme l’envoi à tous les utilisateurs.',
            parse_mode=ParseMode.HTML,
            reply_markup=broadcast_confirm(),
        )
    elif kind == 'forbidden_word' and update.message.text:
        word = update.message.text.strip()
        async with SessionLocal() as s:
            if not await s.scalar(select(ForbiddenWord).where(func.lower(ForbiddenWord.word) == word.lower())):
                s.add(ForbiddenWord(word=word, exact_word=True))
                await s.commit()
        context.user_data.pop('admin_input', None)
        await update.message.reply_text('✅ Mot interdit ajouté.', reply_markup=admin_menu())


async def my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmu = update.my_chat_member
    if not cmu or cmu.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    new = cmu.new_chat_member.status
    old = cmu.old_chat_member.status
    actor = cmu.from_user
    chat = cmu.chat
    if new in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR) and old in (ChatMember.LEFT, ChatMember.BANNED):
        trusted = await is_admin(actor.id)
        if not trusted:
            link = await public_group_link(context.bot, chat)
            await notify_admins(context.bot, f'🚨 <b>Tentative de raccordement non autorisée</b>\n\nGroupe : {chat.title}\nAjouté par : @{actor.username or actor.id}\nLien : {link}')
            try:
                await context.bot.send_message(chat.id, 'Garde la pêche 👋')
                await context.bot.leave_chat(chat.id)
            except TelegramError:
                pass
            return
        async with SessionLocal() as s:
            g = await s.get(Group, chat.id)
            if not g:
                g = Group(chat_id=chat.id, title=chat.title or str(chat.id), username=chat.username, source_token=token())
                s.add(g)
            elif g.role == GroupRole.blocked:
                # Un ancien groupe perdu peut être rebranché et reconfiguré proprement.
                g.role = GroupRole.pending
                g.authorized = False
                g.health_error = None
            g.title = chat.title or str(chat.id)
            g.username = chat.username
            g.last_health_ok = True
            g.last_seen_at = now()
            await s.commit()
        await notify_admins(context.bot, f'✅ <b>Nouveau groupe détecté</b>\n\n{chat.title}\nPromouvez le bot administrateur puis choisissez son rôle.', pending_group(chat.id, new == ChatMember.ADMINISTRATOR))
    elif new in (ChatMember.LEFT, ChatMember.BANNED):
        async with SessionLocal() as s:
            g = await s.get(Group, chat.id)
            role = g.role if g else None
            if g:
                g.last_health_ok = False
                g.health_error = 'bot retiré ou banni'
                await s.commit()
        release = {'campaigns': 0, 'links': 0, 'invites': 0, 'users': 0}
        if role == GroupRole.pub:
            release = await release_lost_pub_group(context.bot, chat.id, 'bot retiré ou banni')
        await notify_admins(
            context.bot,
            f'🚨 <b>Le bot a perdu la trace d’un groupe</b>\n\n'
            f'Groupe : {chat.title}\nID : <code>{chat.id}</code>\n'
            f'Campagnes libérées : {release["campaigns"]}\n'
            f'Liens révoqués : {release["links"]}\n'
            f'Utilisateurs notifiés : {release["users"]}'
        )


async def member_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmu = update.chat_member
    if not cmu or cmu.from_user.id == context.bot.id:
        return
    chat_id = cmu.chat.id
    async with SessionLocal() as sdb:
        group = await sdb.get(Group, chat_id)
    if not group:
        return
    old, new = cmu.old_chat_member.status, cmu.new_chat_member.status
    joined = old in (ChatMember.LEFT, ChatMember.BANNED) and new in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.RESTRICTED)
    if not joined:
        return
    user = cmu.new_chat_member.user

    if group.role == GroupRole.pub and cmu.invite_link:
        async with SessionLocal() as sdb:
            camp = await sdb.scalar(select(Campaign).where(Campaign.invite_link == cmu.invite_link.invite_link, Campaign.status == CampaignStatus.active))
            if not camp or camp.user_id == user.id:
                return
            exists = await sdb.scalar(select(Invite).where(Invite.joined_user_id == user.id))
            if exists:
                camp.invalid_invites += 1
                sdb.add(MetricEvent(event_type=EventType.invite_invalid, pub_group_id=group.chat_id, user_id=camp.user_id))
                await sdb.commit()
                return
            bad = await forbidden_match(user)
            if bad:
                inviter = await sdb.get(User, camp.user_id)
                inviter.forbidden_invites += 1
                camp.invalid_invites += 1
                sdb.add(Invite(campaign_id=camp.id, joined_user_id=user.id, joined_username=user.username, joined_name=user.full_name, status=InviteStatus.forbidden_profile, validate_after=now(), reason='profil non conforme'))
                if inviter.forbidden_invites >= 3:
                    inviter.banned = True
                    camp.status = CampaignStatus.banned
                    try:
                        await context.bot.send_message(camp.user_id, '⛔ Tu n’as pas invité des personnes FR valides. Tu es banni.')
                    except TelegramError:
                        pass
                await sdb.commit()
                return
            sdb.add(Invite(campaign_id=camp.id, joined_user_id=user.id, joined_username=user.username, joined_name=user.full_name, validate_after=now() + timedelta(minutes=settings.validation_minutes)))
            camp.pending_invites += 1
            await sdb.commit()
        return

    if group.role != GroupRole.vip:
        return

    used_link = cmu.invite_link.invite_link if cmu.invite_link else None
    async with SessionLocal() as sdb:
        trial = None
        if used_link:
            trial = await sdb.scalar(select(TrialAccess).where(TrialAccess.invite_link == used_link, TrialAccess.user_id == user.id, TrialAccess.status == TrialStatus.link_created))
        if trial:
            trial.status = TrialStatus.active
            trial.started_at = now()
            trial.expires_at = now() + timedelta(minutes=settings.trial_minutes)
            camp = await sdb.get(Campaign, trial.campaign_id)
            sdb.add(MetricEvent(event_type=EventType.trial_join, pub_group_id=camp.pub_group_id, user_id=user.id))
            await sdb.commit()
            return

        session = None
        if used_link:
            session = await sdb.scalar(select(VipSession).where(VipSession.invite_link == used_link, VipSession.user_id == user.id, VipSession.status == VipSessionStatus.link_created))
        if session:
            camp = await sdb.get(Campaign, session.campaign_id)
            minutes = max(0, camp.minutes_earned - camp.minutes_consumed)
            if minutes >= settings.minimum_minutes:
                session.status = VipSessionStatus.active
                session.started_at = now()
                session.expires_at = now() + timedelta(minutes=minutes)
                session.allocated_minutes = minutes
                camp.minutes_consumed += minutes
                sdb.add(MetricEvent(event_type=EventType.vip_join, pub_group_id=camp.pub_group_id, user_id=user.id))
                await sdb.commit()
                return

    # Toute entrée ne correspondant pas à un lien actif est retirée immédiatement.
    try:
        await context.bot.ban_chat_member(group.chat_id, user.id)
        await context.bot.unban_chat_member(group.chat_id, user.id, only_if_banned=True)
        await record(EventType.unauthorized_join, user_id=user.id)
    except TelegramError as exc:
        await notify_admins(context.bot, f'🚨 <b>Entrée VIP non autorisée</b>\nUtilisateur : <code>{user.id}</code>\nExpulsion impossible : {exc}')


async def delete_vip_service_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Supprime les messages Telegram « X a rejoint/quitté » dans les groupes VIP."""
    message = update.effective_message
    if not message:
        return
    async with SessionLocal() as sdb:
        group = await sdb.get(Group, message.chat_id)
    if not group or group.role != GroupRole.vip or not group.authorized:
        return
    try:
        await message.delete()
    except TelegramError as exc:
        # Une alerte persistante sera aussi visible dans le bouton Santé.
        log.warning('Impossible de supprimer une notification de service VIP dans %s: %s', message.chat_id, exc)


async def validate_invites(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with SessionLocal() as s:
        invites = list((await s.scalars(select(Invite).where(Invite.status == InviteStatus.pending, Invite.validate_after <= now()).limit(200))).all())
        for inv in invites:
            camp = await s.get(Campaign, inv.campaign_id)
            try:
                member = await context.bot.get_chat_member(camp.pub_group_id, inv.joined_user_id)
                valid = member.status not in (ChatMember.LEFT, ChatMember.BANNED)
            except TelegramError:
                valid = False
            camp.pending_invites = max(0, camp.pending_invites - 1)
            inv.validated_at = now()
            if valid:
                inv.status = InviteStatus.valid; camp.valid_invites += 1; camp.minutes_earned += 1
                s.add(MetricEvent(event_type=EventType.invite_valid, pub_group_id=camp.pub_group_id, user_id=camp.user_id))
                active = await s.scalar(select(VipSession).where(VipSession.campaign_id == camp.id, VipSession.status == VipSessionStatus.active))
                if active and active.expires_at:
                    active.expires_at += timedelta(minutes=1)
                    try: await context.bot.send_message(camp.user_id, f'🎉 Nouvelle invitation validée !\n+1 minute ajoutée. Nouvelle fin prévue : {active.expires_at:%H:%M}.')
                    except TelegramError: pass
            else:
                inv.status = InviteStatus.invalid; camp.invalid_invites += 1; inv.reason = 'départ avant validation'
                s.add(MetricEvent(event_type=EventType.invite_invalid, pub_group_id=camp.pub_group_id, user_id=camp.user_id))
        await s.commit()


async def _kick_and_verify(bot, chat_id: int, user_id: int) -> tuple[bool, str | None]:
    try:
        await bot.ban_chat_member(chat_id, user_id)
        await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMember.LEFT, ChatMember.BANNED), None
    except TelegramError as exc:
        return False, str(exc)


async def expire_trials(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with SessionLocal() as sdb:
        trials = list((await sdb.scalars(select(TrialAccess).where(TrialAccess.status.in_([TrialStatus.active, TrialStatus.kick_pending]), TrialAccess.expires_at <= now()).limit(100))).all())
        for trial in trials:
            trial.status = TrialStatus.kick_pending
            trial.kick_attempts += 1
            ok, error = await _kick_and_verify(context.bot, trial.vip_group_id, trial.user_id)
            camp = await sdb.get(Campaign, trial.campaign_id)
            available = max(0, camp.minutes_earned - camp.minutes_consumed)

            # Si l'utilisateur a atteint le seuil pendant son aperçu, son accès
            # continue automatiquement sans expulsion. Tout son crédit disponible
            # devient une session VIP normale à partir de maintenant.
            if available >= settings.minimum_minutes:
                trial.status = TrialStatus.cancelled
                trial.last_kick_error = None
                session = VipSession(
                    campaign_id=camp.id,
                    user_id=trial.user_id,
                    vip_group_id=trial.vip_group_id,
                    status=VipSessionStatus.active,
                    started_at=now(),
                    expires_at=now() + timedelta(minutes=available),
                    allocated_minutes=available,
                )
                camp.minutes_consumed += available
                sdb.add(session)
                sdb.add(MetricEvent(event_type=EventType.vip_join, pub_group_id=camp.pub_group_id, user_id=trial.user_id))
                try:
                    await context.bot.send_message(
                        trial.user_id,
                        '🎉 <b>Félicitations !</b>\n\n'
                        'Tu as déjà obtenu suffisamment d’invitations.\n'
                        'Ton accès découverte continue automatiquement en accès VIP.\n\n'
                        f'⏱ Temps ajouté : <b>{available} minute(s)</b>\n\n'
                        'Continue à inviter : chaque nouvelle invitation validée prolongera ton accès d’une minute.',
                        parse_mode=ParseMode.HTML,
                        reply_markup=user_menu(False, 0),
                    )
                except TelegramError:
                    pass
                continue

            if ok:
                trial.status = TrialStatus.kicked
                trial.kick_verified_at = now()
                trial.last_kick_error = None
                sdb.add(MetricEvent(event_type=EventType.trial_kick, pub_group_id=camp.pub_group_id, user_id=trial.user_id))
                missing = max(0, settings.minimum_minutes - available)
                try:
                    await context.bot.send_message(
                        trial.user_id,
                        '⏳ <b>Ton accès découverte est terminé !</b>\n\n'
                        'Tu as pu découvrir une partie du VIP. Il reste encore beaucoup de contenu à voir.\n\n'
                        'La bonne nouvelle : tu peux revenir gratuitement autant de fois que tu le souhaites.\n\n'
                        '🎁 <b>1 invitation validée = 1 minute de VIP</b>\n'
                        f'🔐 Il faut au moins <b>{settings.minimum_minutes} invitations validées</b> pour revenir.\n\n'
                        '━━━━━━━━━━━━━━\n'
                        '📊 <b>Ton compteur</b>\n\n'
                        f'✅ Invitations validées : <b>{camp.valid_invites}</b>\n'
                        f'⏳ En vérification : <b>{camp.pending_invites}</b>\n'
                        f'❌ Non validées : <b>{camp.invalid_invites}</b>\n\n'
                        f'⏱ Crédit disponible : <b>{available} minute(s)</b>\n'
                        f'🎯 Encore <b>{missing}</b> invitation(s) pour revenir dans le VIP.\n\n'
                        '━━━━━━━━━━━━━━\n'
                        '🔗 <b>Ton lien personnel</b>\n\n'
                        f'<code>{camp.invite_link}</code>\n\n'
                        'Partage-le où tu le souhaites. Chaque personne validée te rapporte une minute.',
                        parse_mode=ParseMode.HTML,
                        reply_markup=user_menu(False, missing),
                        disable_web_page_preview=True,
                    )
                except TelegramError:
                    pass
            else:
                trial.last_kick_error = error
                if trial.kick_attempts == 1 or trial.kick_attempts % 3 == 0:
                    await notify_admins(context.bot, f'❌ <b>Essai VIP non expulsé</b>\nUtilisateur : <code>{trial.user_id}</code>\nTentative : {trial.kick_attempts}\nErreur : {error}')
        await sdb.commit()


async def expire_sessions(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with SessionLocal() as sdb:
        sessions = list((await sdb.scalars(select(VipSession).where(VipSession.status.in_([VipSessionStatus.active, VipSessionStatus.kick_pending]), VipSession.expires_at <= now()).limit(100))).all())
        for session in sessions:
            session.status = VipSessionStatus.kick_pending
            session.kick_attempts += 1
            ok, error = await _kick_and_verify(context.bot, session.vip_group_id, session.user_id)
            if ok:
                session.status = VipSessionStatus.kicked
                session.last_kick_error = None
                camp = await sdb.get(Campaign, session.campaign_id)
                sdb.add(MetricEvent(event_type=EventType.vip_kick, pub_group_id=camp.pub_group_id, user_id=session.user_id))
                try:
                    await context.bot.send_message(
                        session.user_id,
                        f'⌛ Ton temps VIP est terminé.\n\nContinue à inviter pour gagner de nouvelles minutes. Il faut au moins {settings.minimum_minutes} minutes pour revenir.',
                        reply_markup=user_menu(False, settings.minimum_minutes),
                    )
                except TelegramError:
                    pass
            else:
                session.last_kick_error = error
                if session.kick_attempts == 1 or session.kick_attempts % 3 == 0:
                    await notify_admins(context.bot, f'❌ <b>Expulsion VIP impossible</b>\nUtilisateur : <code>{session.user_id}</code>\nTentative : {session.kick_attempts}\nErreur : {error}')
        await sdb.commit()


async def audit_vip_members(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Contrôle de rattrapage des expulsions non confirmées."""
    async with SessionLocal() as sdb:
        bad_trials = int(await sdb.scalar(select(func.count(TrialAccess.id)).where(TrialAccess.status == TrialStatus.kick_pending)) or 0)
        bad_sessions = int(await sdb.scalar(select(func.count(VipSession.id)).where(VipSession.status == VipSessionStatus.kick_pending)) or 0)
    if bad_trials or bad_sessions:
        await notify_admins(context.bot, f'⚠️ <b>Contrôle des expulsions</b>\nEssais en attente : {bad_trials}\nSessions en attente : {bad_sessions}\nLe bot continue les nouvelles tentatives automatiquement.')


async def run_broadcast(bot, admin_id: int, source_chat_id: int, source_message_id: int) -> None:
    async with SessionLocal() as sdb:
        user_ids = list((await sdb.scalars(select(User.telegram_id).order_by(User.telegram_id))).all())
    sent = blocked = errors = 0
    for uid in user_ids:
        while True:
            try:
                await bot.copy_message(uid, source_chat_id, source_message_id)
                sent += 1
                break
            except RetryAfter as exc:
                await asyncio.sleep(float(exc.retry_after) + 0.5)
            except Forbidden:
                blocked += 1
                break
            except (BadRequest, TelegramError):
                errors += 1
                break
        await asyncio.sleep(max(0.0, settings.broadcast_delay_seconds))
    try:
        await bot.send_message(
            admin_id,
            '✅ <b>Broadcast terminé</b>\n\n'
            f'Envoyés : {sent}\n'
            f'Utilisateurs ayant bloqué le bot : {blocked}\n'
            f'Autres erreurs : {errors}',
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu(),
        )
    except TelegramError:
        pass


async def send_health(message, context) -> None:
    lines = ['🩺 <b>SANTÉ DU SYSTÈME</b>', '', f'🎁 Essai découverte : {settings.trial_minutes} minute(s)', f'🔁 Contrôle expulsions : toutes les {settings.kick_retry_seconds} seconde(s)', '']
    try:
        me = await context.bot.get_me(); lines.append(f'🟢 Telegram : @{me.username}')
    except TelegramError as exc:
        lines.append(f'🔴 Telegram : {exc}')
    try:
        async with engine.connect() as conn: await conn.execute(select(1))
        lines.append('🟢 PostgreSQL : connectée')
    except Exception as exc:
        lines.append(f'🔴 PostgreSQL : {exc}')
    async with SessionLocal() as s:
        pubs = list((await s.scalars(select(Group).where(Group.role == GroupRole.pub, Group.authorized.is_(True)))).all())
        vips = list((await s.scalars(select(Group).where(Group.role == GroupRole.vip, Group.authorized.is_(True)))).all())
    lines.append(f'{"🟢" if pubs else "🔴"} Groupes PUB : {len(pubs)}')
    lines.append(f'{"🟢" if vips else "🔴"} Groupes VIP : {len(vips)}')
    for g in vips + pubs:
        ok, reason = await bot_rights(context.bot, g.chat_id, require_delete=(g.role == GroupRole.vip))
        association = ''
        if g.role == GroupRole.pub and not g.vip_group_id:
            ok, reason = False, 'aucun VIP associé'
        lines.append(f'{"🟢" if ok else "🔴"} {g.title} — {reason}')
    async with SessionLocal() as sdb:
        pending_trials = int(await sdb.scalar(select(func.count(TrialAccess.id)).where(TrialAccess.status == TrialStatus.kick_pending)) or 0)
        pending_sessions = int(await sdb.scalar(select(func.count(VipSession.id)).where(VipSession.status == VipSessionStatus.kick_pending)) or 0)
    lines.append(f'{"🟢" if pending_trials == 0 else "🔴"} Essais à expulser : {pending_trials}')
    lines.append(f'{"🟢" if pending_sessions == 0 else "🔴"} Sessions à expulser : {pending_sessions}')
    rec = context.application.bot_data.get('last_lost_reconciliation', {})
    if rec:
        lines.append('')
        lines.append('🧹 Dernière réconciliation des groupes perdus')
        lines.append(f'Campagnes libérées : {rec.get("campaigns", 0)}')
        lines.append(f'Liens révoqués : {rec.get("links", 0)}')
        lines.append(f'Utilisateurs notifiés : {rec.get("users", 0)}')
    await message.reply_text('\n'.join(lines), parse_mode=ParseMode.HTML)


async def health_watch(context: ContextTypes.DEFAULT_TYPE) -> None:
    grace = timedelta(minutes=settings.group_lost_grace_minutes)
    async with SessionLocal() as s:
        groups = list((await s.scalars(select(Group).where(
            Group.authorized.is_(True), Group.role.in_([GroupRole.pub, GroupRole.vip])
        ))).all())

    for group in groups:
        ok, reason = await bot_rights(
            context.bot, group.chat_id, require_delete=(group.role == GroupRole.vip)
        )
        connection_ok = ok
        configuration_error = group.role == GroupRole.pub and not group.vip_group_id

        async with SessionLocal() as s:
            g = await s.get(Group, group.chat_id)
            if not g:
                continue
            changed_to_error = g.last_health_ok and not connection_ok
            changed_to_ok = not g.last_health_ok and connection_ok
            g.last_health_ok = connection_ok
            g.health_error = None if connection_ok else reason
            if connection_ok:
                g.last_seen_at = now()
            await s.commit()

        if changed_to_error:
            await notify_admins(
                context.bot,
                f'⚠️ <b>Connexion au groupe à vérifier</b>\n\n'
                f'{group.title}\nID : <code>{group.chat_id}</code>\nErreur : {reason}\n\n'
                f'La libération automatique aura lieu si la perte est toujours confirmée après '
                f'{settings.group_lost_grace_minutes} minute(s).',
            )
        elif changed_to_ok:
            await notify_admins(context.bot, f'✅ Connexion rétablie : <b>{group.title}</b>')

        if (not connection_ok and group.role == GroupRole.pub and
                _connection_loss_reason(reason) and
                (group.last_seen_at is None or now() - group.last_seen_at >= grace)):
            result = await release_lost_pub_group(context.bot, group.chat_id, reason)
            if result['campaigns'] or result['users'] or result['links']:
                await notify_admins(
                    context.bot,
                    f'🧹 <b>Groupe PUB confirmé perdu</b>\n\n'
                    f'{group.title}\nID : <code>{group.chat_id}</code>\n'
                    f'Campagnes libérées : {result["campaigns"]}\n'
                    f'Liens révoqués : {result["links"]}\n'
                    f'Invitations annulées : {result["invites"]}\n'
                    f'Utilisateurs notifiés : {result["users"]}',
                )

    await reconcile_lost_groups(context)


async def send_group_stats(message, gid: int) -> None:
    end = now(); start = end - timedelta(days=7); prev = start - timedelta(days=7)
    async with SessionLocal() as s:
        g = await s.get(Group, gid)
        async def count(event, a, b):
            return int(await s.scalar(select(func.count(MetricEvent.id)).where(MetricEvent.pub_group_id == gid, MetricEvent.event_type == event, MetricEvent.created_at >= a, MetricEvent.created_at < b)) or 0)
        clicks = await count(EventType.ad_click, start, end); old_clicks = await count(EventType.ad_click, prev, start)
        campaigns = await count(EventType.campaign_started, start, end); invites = await count(EventType.invite_valid, start, end); vip = await count(EventType.vip_join, start, end)
    change = 0 if old_clicks == 0 else ((clicks - old_clicks) / old_clicks * 100)
    trend = '🟢 hausse' if change > 10 else '🔴 perte d’intérêt' if change <= -settings.trend_drop_percent else '🟠 stable'
    await message.reply_text(
        f'📢 <b>{g.title}</b> — 7 jours\n\n👆 Clics : {clicks}\n🚀 Campagnes : {campaigns}\n✅ Invitations : {invites}\n🔐 Entrées VIP : {vip}\n\nÉvolution des clics : {change:+.1f}%\nDiagnostic : {trend}', parse_mode=ParseMode.HTML)


async def send_global_stats(message) -> None:
    since = now() - timedelta(days=7)
    async with SessionLocal() as s:
        campaigns = int(await s.scalar(select(func.count(Campaign.id)).where(Campaign.created_at >= since)) or 0)
        valid = int(await s.scalar(select(func.count(Invite.id)).where(Invite.status == InviteStatus.valid, Invite.validated_at >= since)) or 0)
        sessions = int(await s.scalar(select(func.count(VipSession.id)).where(VipSession.started_at >= since)) or 0)
        kicked = int(await s.scalar(select(func.count(VipSession.id)).where(VipSession.status == VipSessionStatus.kicked, VipSession.updated_at >= since)) or 0)
        errors = int(await s.scalar(select(func.count(VipSession.id)).where(VipSession.status == VipSessionStatus.kick_pending)) or 0)
    await message.reply_text(f'📊 <b>STATISTIQUES — 7 JOURS</b>\n\nCampagnes : {campaigns}\nInvitations validées : {valid}\nSessions VIP : {sessions}\nExpulsions réussies : {kicked}\nExpulsions en attente/erreur : {errors}', parse_mode=ParseMode.HTML)


async def post_init(app: Application) -> None:
    settings.validate(); await init_db()
    async with SessionLocal() as s:
        for uid in settings.owner_ids:
            if not await s.get(Admin, uid): s.add(Admin(telegram_id=uid, source='owner'))
        await s.commit()
    app.job_queue.run_repeating(validate_invites, interval=30, first=10, name='validate_invites')
    app.job_queue.run_repeating(expire_trials, interval=settings.kick_retry_seconds, first=10, name='expire_trials')
    app.job_queue.run_repeating(expire_sessions, interval=settings.kick_retry_seconds, first=15, name='expire_sessions')
    app.job_queue.run_repeating(audit_vip_members, interval=300, first=120, name='audit_vip_members')
    app.job_queue.run_repeating(health_watch, interval=settings.health_interval_minutes * 60, first=30, name='health_watch')
    app.job_queue.run_once(reconcile_lost_groups, when=8, name='reconcile_lost_groups_startup')


def build() -> Application:
    app = Application.builder().token(settings.bot_token).post_init(post_init).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(ChatMemberHandler(my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(member_update, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER, delete_vip_service_message))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & filters.ChatType.PRIVATE, admin_input))
    return app


if __name__ == '__main__':
    build().run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
