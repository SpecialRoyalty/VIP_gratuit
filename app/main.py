from __future__ import annotations

import logging
import random
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from telegram import ChatMember, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import settings
from .db import SessionLocal, init_db
from .keyboards import admin_menu, group_role_keyboard, proof_menu, proof_review_keyboard, start_menu, user_menu, group_manage_keyboard, groups_list_keyboard, vip_choice_keyboard, promote_required_keyboard
from .models import Admin, Campaign, CampaignStatus, Group, GroupRole, Invite, InviteStatus, Proof, ProofStatus, Reminder, User
from .texts import publication_text

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger(__name__)
UTC = timezone.utc
ACTIVE_STATUSES = (CampaignStatus.awaiting_proof, CampaignStatus.proof_review, CampaignStatus.active, CampaignStatus.vip_active)



async def bot_admin_check(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> tuple[bool, str]:
    """Vérifie que le bot est administrateur et possède les droits essentiels."""
    try:
        member = await context.bot.get_chat_member(chat_id, context.bot.id)
    except TelegramError as exc:
        return False, f'inaccessible ({exc})'
    if member.status == ChatMember.OWNER:
        return True, 'propriétaire'
    if member.status != ChatMember.ADMINISTRATOR:
        return False, 'le bot n’est pas administrateur'
    missing = []
    if not getattr(member, 'can_invite_users', False):
        missing.append('inviter via des liens')
    if missing:
        return False, 'droit manquant : ' + ', '.join(missing)
    return True, 'administrateur, liens d’invitation autorisés'


def now() -> datetime:
    return datetime.now(UTC)


async def is_admin(user_id: int) -> bool:
    if user_id in settings.owner_ids:
        return True
    async with SessionLocal() as s:
        return bool(await s.scalar(select(Admin.telegram_id).where(Admin.telegram_id == user_id, Admin.active.is_(True))))


async def upsert_user(tg_user) -> None:
    async with SessionLocal() as s:
        user = await s.get(User, tg_user.id)
        if not user:
            user = User(telegram_id=tg_user.id)
            s.add(user)
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        await s.commit()


async def active_campaign(user_id: int) -> Campaign | None:
    async with SessionLocal() as s:
        return await s.scalar(select(Campaign).where(Campaign.user_id == user_id, Campaign.status.in_(ACTIVE_STATUSES)))


async def send_publication_text(update: Update, campaign: Campaign) -> None:
    text = publication_text(campaign.phrase_index, campaign.invite_link)
    msg = (
        '📋 <b>Voici ton texte personnel</b>\n\n'
        'Copie et colle la phrase ci-dessous <b>exactement telle qu’elle est affichée</b>.\n\n'
        '⚠️ Ne retire aucun espace dans le lien.\n'
        '⚠️ Ne modifie aucun caractère.\n\n'
        f'<code>{text}</code>\n\n'
        'Après l’avoir publié sur Leakimedia, envoie une capture d’écran complète de ta publication.'
    )
    target = update.effective_message
    await target.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=proof_menu())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or update.effective_chat.type != ChatType.PRIVATE:
        return
    await upsert_user(update.effective_user)
    if not context.args:
        # Les administrateurs sont détectés automatiquement : /start ouvre directement
        # leur panneau, sans devoir connaître ou saisir la commande /admin.
        if await is_admin(update.effective_user.id):
            await update.message.reply_text(
                '🛠 <b>Panneau administrateur</b>\n\n'
                'Ton compte administrateur a été détecté automatiquement.',
                parse_mode=ParseMode.HTML,
                reply_markup=admin_menu(),
            )
            return
        camp = await active_campaign(update.effective_user.id)
        if camp:
            await update.message.reply_text('🏠 Menu principal', reply_markup=user_menu())
        else:
            await update.message.reply_text('Bienvenue. Ouvre le bouton « VIP GRATUIT » depuis un groupe publicitaire pour commencer.')
        return

    token = context.args[0]
    if not token.startswith('pub_'):
        await update.message.reply_text('Lien de démarrage invalide.')
        return
    source_token = token[4:]
    async with SessionLocal() as s:
        group = await s.scalar(select(Group).where(Group.source_token == source_token, Group.role == GroupRole.pub, Group.authorized.is_(True)))
        existing = await s.scalar(select(Campaign).where(Campaign.user_id == update.effective_user.id, Campaign.status.in_(ACTIVE_STATUSES)))
        if existing:
            if existing.status == CampaignStatus.vip_active:
                expiry = existing.vip_expires_at.strftime('%d/%m/%Y') if existing.vip_expires_at else 'inconnue'
                await update.message.reply_text(f'✅ Tu possèdes déjà un accès VIP actif jusqu’au {expiry}.\nUne seule campagne peut être active.', reply_markup=user_menu())
            else:
                await update.message.reply_text('⚠️ Tu as déjà une campagne en cours. Elle reste associée au premier groupe utilisé.', reply_markup=user_menu())
            return
        if not group or not group.vip_group_id:
            await update.message.reply_text('Cette campagne n’est pas encore correctement configurée.')
            return
        context.user_data['pending_pub_group_id'] = group.chat_id
        intro = group.private_intro or (
            '👋 Bienvenue !\n\nTu peux obtenir gratuitement un accès de 10 jours à notre groupe VIP. '
            'Ce VIP gratuit ne remplace pas le VIP proposé à la vente, mais il reste très intéressant.\n\n'
            f'Chaque tranche de {settings.invite_goal} invitations validées crédite {settings.vip_days_per_goal} jours de VIP.'
        )
        if group.private_photo_file_id:
            await update.message.reply_photo(group.private_photo_file_id, caption=intro, reply_markup=start_menu())
        else:
            await update.message.reply_text(intro, reply_markup=start_menu())


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not await is_admin(update.effective_user.id):
        await update.effective_message.reply_text('Accès refusé.')
        return
    await update.effective_message.reply_text('🛠 Panneau administrateur', reply_markup=admin_menu())


async def configure_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commands: /setad chat_id text, /setintro chat_id text, /linkvip pub_id vip_id."""
    if not update.effective_user or not await is_admin(update.effective_user.id):
        return
    cmd = update.effective_message.text.split(maxsplit=2)
    name = cmd[0].split('@')[0]
    try:
        async with SessionLocal() as s:
            if name in ('/setad', '/setintro') and len(cmd) >= 3:
                gid = int(cmd[1]); text = cmd[2]
                group = await s.get(Group, gid)
                if not group: raise ValueError('groupe introuvable')
                if name == '/setad': group.ad_text = text
                else: group.private_intro = text
            elif name == '/linkvip' and len(cmd) >= 3:
                pub_id = int(cmd[1]); vip_id = int(cmd[2])
                pub = await s.get(Group, pub_id); vip = await s.get(Group, vip_id)
                if not pub or not vip or vip.role != GroupRole.vip: raise ValueError('groupes invalides')
                pub.vip_group_id = vip_id
            else:
                raise ValueError('syntaxe invalide')
            await s.commit()
        await update.effective_message.reply_text('✅ Configuration enregistrée.')
    except Exception as exc:
        await update.effective_message.reply_text(f'Erreur : {exc}')


async def admin_photo_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not await is_admin(update.effective_user.id) or not update.message.photo:
        return
    caption = (update.message.caption or '').strip()
    # Format: #ad -100... or #private -100...
    parts = caption.split()
    if len(parts) != 2 or parts[0] not in ('#ad', '#private'):
        return
    try:
        gid = int(parts[1])
    except ValueError:
        return
    async with SessionLocal() as s:
        group = await s.get(Group, gid)
        if not group:
            await update.message.reply_text('Groupe introuvable.')
            return
        if parts[0] == '#ad': group.ad_photo_file_id = update.message.photo[-1].file_id
        else: group.private_photo_file_id = update.message.photo[-1].file_id
        await s.commit()
    await update.message.reply_text('✅ Image enregistrée.')


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data or ''

    if data == 'u:how':
        await q.message.reply_text(
            f'📖 <b>Comment obtenir ton accès VIP ?</b>\n\n'
            '1️⃣ Le bot crée ton lien personnel.\n'
            '2️⃣ Tu copies le texte fourni sur Leakimedia, sans modifier les espaces.\n'
            '3️⃣ Tu envoies une capture d’écran.\n'
            '4️⃣ Après validation, ton compteur démarre.\n'
            f'5️⃣ Chaque tranche de {settings.invite_goal} invitations validées ajoute {settings.vip_days_per_goal} jours de VIP.\n\n'
            'Une invitation qui ne respecte pas les conditions ne sera pas validée.',
            parse_mode=ParseMode.HTML,
            reply_markup=start_menu(),
        )
        return

    if data == 'u:begin':
        gid = context.user_data.get('pending_pub_group_id')
        if not gid:
            await q.message.reply_text('Reviens depuis le bouton du groupe publicitaire.')
            return
        async with SessionLocal() as s:
            existing = await s.scalar(select(Campaign).where(Campaign.user_id == uid, Campaign.status.in_(ACTIVE_STATUSES)))
            if existing:
                await q.message.reply_text('⚠️ Une campagne est déjà en cours.', reply_markup=user_menu()); return
            group = await s.get(Group, gid)
            if not group or not group.vip_group_id:
                await q.message.reply_text('Configuration incomplète.'); return
            try:
                invite = await context.bot.create_chat_invite_link(group.chat_id, name=f'u{uid}'[:32])
            except TelegramError as exc:
                await q.message.reply_text(f'Impossible de créer le lien. Vérifie les droits administrateur du bot. ({exc})'); return
            camp = Campaign(user_id=uid, pub_group_id=gid, vip_group_id=group.vip_group_id, invite_link=invite.invite_link, phrase_index=random.randrange(10))
            s.add(camp)
            try:
                await s.commit(); await s.refresh(camp)
            except IntegrityError:
                await s.rollback(); await q.message.reply_text('Une campagne est déjà en cours.'); return
        await q.message.reply_text('✅ Ton lien personnel a été créé. Publie maintenant le texte sur https://leakimedia.com/.')
        await send_publication_text(update, camp)
        return

    camp = await active_campaign(uid)
    if data in ('u:counter', 'u:text', 'u:proof', 'u:vip', 'u:help', 'u:help_publish') and not camp:
        await q.message.reply_text('Aucune campagne active.'); return
    if data == 'u:counter':
        pct = min(100, int((camp.valid_count % settings.invite_goal) * 100 / settings.invite_goal))
        next_goal = ((camp.valid_count // settings.invite_goal) + 1) * settings.invite_goal
        await q.message.reply_text(
            f'📊 <b>Ta progression</b>\n\nValidées : {camp.valid_count}\nEn attente : {camp.pending_count}\n'
            f'Non validées : {camp.invalid_count}\nProchain palier : {next_goal}\nProgression du palier : {pct} %',
            parse_mode=ParseMode.HTML, reply_markup=user_menu())
    elif data == 'u:text':
        await send_publication_text(update, camp)
    elif data == 'u:proof':
        await q.message.reply_text('📸 Envoie maintenant ta capture d’écran sous forme de photo dans cette conversation.')
    elif data == 'u:vip':
        if camp.status != CampaignStatus.vip_active:
            await q.message.reply_text(f'🔒 Le VIP sera débloqué à {settings.invite_goal} invitations validées.')
        else:
            await q.message.reply_text(f'🔐 Accès actif jusqu’au {camp.vip_expires_at.strftime("%d/%m/%Y %H:%M")}.')
    elif data in ('u:help', 'u:help_publish'):
        await q.message.reply_text('Copie toute la phrase, conserve exactement les espaces, publie-la sur Leakimedia puis envoie une capture complète.')
    elif data == 'u:cancel':
        context.user_data.pop('pending_pub_group_id', None)
        await q.message.reply_text('Parcours annulé.')

    if data.startswith('a:'):
        if not await is_admin(uid):
            await q.message.reply_text('Accès refusé.'); return
        await admin_callback(update, context)


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query; data = q.data
    if data == 'a:health':
        telegram_ok = database_ok = False
        bot_name = 'inconnu'
        try:
            me = await context.bot.get_me(); telegram_ok = True
            bot_name = f'@{me.username}' if me.username else me.full_name
        except TelegramError as exc:
            log.warning('Health Telegram échoué: %s', exc)

        groups = []
        active_campaigns = vip_active = valid_today = 0
        try:
            async with SessionLocal() as s:
                await s.scalar(select(func.count()).select_from(User)); database_ok = True
                groups = (await s.scalars(select(Group).where(Group.authorized.is_(True)).order_by(Group.role, Group.title))).all()
                active_campaigns = await s.scalar(select(func.count()).select_from(Campaign).where(Campaign.status.in_(ACTIVE_STATUSES))) or 0
                vip_active = await s.scalar(select(func.count()).select_from(Campaign).where(Campaign.status == CampaignStatus.vip_active)) or 0
                day_start = now().replace(hour=0, minute=0, second=0, microsecond=0)
                valid_today = await s.scalar(select(func.count()).select_from(Invite).where(Invite.status == InviteStatus.valid, Invite.validated_at >= day_start)) or 0
        except Exception as exc:
            log.exception('Health PostgreSQL échoué: %s', exc)

        pub_groups = [g for g in groups if g.role == GroupRole.pub]
        vip_groups = [g for g in groups if g.role == GroupRole.vip]
        checks = {}
        for g in pub_groups + vip_groups:
            checks[g.chat_id] = await bot_admin_check(context, g.chat_id)

        all_pub_admin = bool(pub_groups) and all(checks[g.chat_id][0] for g in pub_groups)
        all_pub_linked = bool(pub_groups) and all(g.vip_group_id for g in pub_groups)
        vip_ok = bool(vip_groups) and any(checks[g.chat_id][0] for g in vip_groups)
        overall = telegram_ok and database_ok and vip_ok and all_pub_admin and all_pub_linked
        lines = [
            f"{'✅' if overall else '⚠️'} <b>État du système</b>", '',
            '<b>Infrastructure</b>',
            f"{'🟢' if telegram_ok else '🔴'} Telegram : {'connecté' if telegram_ok else 'indisponible'} ({bot_name})",
            f"{'🟢' if database_ok else '🔴'} PostgreSQL : {'connectée' if database_ok else 'indisponible'}", '',
            '<b>Groupes PUB</b>'
        ]
        if not pub_groups:
            lines.append('⚠️ Aucun groupe publicitaire configuré')
        for g in pub_groups:
            ok, detail = checks[g.chat_id]
            linked = bool(g.vip_group_id)
            lines.extend([
                f"{'🟢' if ok and linked else '🔴'} {g.title}",
                f"  Admin : {'Oui' if ok else 'Non'} — {detail}",
                f"  VIP associé : {'Oui' if linked else 'Non'}",
            ])
        lines.extend(['', '<b>VIP</b>'])
        if not vip_groups:
            lines.append('🔴 Aucun groupe VIP configuré')
        for g in vip_groups:
            ok, detail = checks[g.chat_id]
            lines.extend([f"{'🟢' if ok else '🔴'} {g.title}", f"  Bot admin : {'Oui' if ok else 'Non'} — {detail}"])
        lines.extend([
            '', '<b>Tâches automatiques</b>',
            '🟢 Vérification des invitations après 5 minutes',
            '🟢 Rappels avant expiration',
            '🟢 Expiration et retrait VIP',
            '', '<b>Activité</b>',
            f'Campagnes actives : {active_campaigns}',
            f'VIP actifs : {vip_active}',
            f'Invitations validées aujourd’hui : {valid_today}',
        ])
        await q.message.reply_text('\n'.join(lines), parse_mode=ParseMode.HTML, reply_markup=admin_menu())
    elif data == 'a:menu':
        await q.message.reply_text('🛠 Panneau administrateur', reply_markup=admin_menu())
    elif data == 'a:groups':
        async with SessionLocal() as s:
            groups = (await s.scalars(select(Group).order_by(Group.created_at.desc()).limit(50))).all()
        if not groups: await q.message.reply_text('Aucun groupe détecté.'); return
        await q.message.reply_text('👥 <b>Choisis un groupe à configurer</b>', parse_mode=ParseMode.HTML, reply_markup=groups_list_keyboard(groups))
    elif data.startswith('a:group:'):
        gid = int(data.split(':')[2])
        async with SessionLocal() as s:
            g = await s.get(Group, gid)
            vip = await s.get(Group, g.vip_group_id) if g and g.vip_group_id else None
        if not g:
            await q.message.reply_text('Groupe introuvable.'); return
        admin_ok, admin_detail = await bot_admin_check(context, g.chat_id)
        status = (
            f'⚙️ <b>{g.title}</b>\n\n'
            f'ID : <code>{g.chat_id}</code>\n'
            f'Rôle : {g.role.value}\n'
            f'Bot administrateur : {"✅" if admin_ok else "❌"} ({admin_detail})\n'
            f'Texte de pub : {"✅" if g.ad_text else "❌"}\n'
            f'Image de pub : {"✅" if g.ad_photo_file_id else "❌"}\n'
            f'Texte privé : {"✅" if g.private_intro else "❌"}\n'
            f'Image privée : {"✅" if g.private_photo_file_id else "❌"}\n'
            f'VIP associé : {vip.title if vip else "❌ Aucun"}'
        )
        markup = group_manage_keyboard(g.chat_id, g.role.value) if g.role != GroupRole.pending else group_role_keyboard(g.chat_id)
        await q.message.reply_text(status, parse_mode=ParseMode.HTML, reply_markup=markup)
    elif data.startswith('a:cfg:'):
        _, _, gid_s, action = data.split(':', 3); gid = int(gid_s)
        if action in ('ad_text', 'private_text'):
            context.user_data['admin_input'] = {'group_id': gid, 'kind': action}
            label = 'texte de publicité' if action == 'ad_text' else 'texte affiché en privé au démarrage'
            await q.message.reply_text(f'✍️ Envoie maintenant le {label} dans ton prochain message.\n\nUtilise /annuler pour abandonner.')
        elif action in ('ad_photo', 'private_photo'):
            context.user_data['admin_input'] = {'group_id': gid, 'kind': action}
            label = 'image de publicité' if action == 'ad_photo' else 'image affichée en privé au démarrage'
            await q.message.reply_text(f'🖼 Envoie maintenant la {label} sous forme de photo.\n\nUtilise /annuler pour abandonner.')
        elif action == 'vip':
            async with SessionLocal() as s:
                vips = (await s.scalars(select(Group).where(Group.role == GroupRole.vip, Group.authorized.is_(True)))).all()
            if not vips:
                await q.message.reply_text('Aucun groupe VIP configuré. Déclare d’abord un groupe comme VIP.'); return
            await q.message.reply_text('Choisis le VIP commun à associer à ce groupe publicitaire :', reply_markup=vip_choice_keyboard(gid, vips))
        elif action in ('preview', 'publish'):
            async with SessionLocal() as s:
                g = await s.get(Group, gid)
            if not g:
                await q.message.reply_text('Groupe introuvable.'); return
            me = await context.bot.get_me(); url = f'https://t.me/{me.username}?start=pub_{g.source_token}'
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('🎁 VIP GRATUIT', url=url)]])
            target = q.from_user.id if action == 'preview' else g.chat_id
            try:
                if g.ad_photo_file_id:
                    await context.bot.send_photo(target, g.ad_photo_file_id, caption=g.ad_text or 'Débloque ton VIP gratuit.', reply_markup=kb)
                else:
                    await context.bot.send_message(target, g.ad_text or 'Débloque ton VIP gratuit.', reply_markup=kb)
                await q.message.reply_text('✅ Prévisualisation envoyée.' if action == 'preview' else '✅ Publicité publiée dans ce groupe.')
            except TelegramError as exc:
                await q.message.reply_text(f'❌ Envoi impossible : {exc}')
    elif data.startswith('a:setvip:'):
        _, _, pub_s, vip_s = data.split(':'); pub_id = int(pub_s); vip_id = int(vip_s)
        async with SessionLocal() as s:
            pub = await s.get(Group, pub_id); vip = await s.get(Group, vip_id)
            if not pub or not vip or vip.role != GroupRole.vip:
                await q.message.reply_text('Association invalide.'); return
            pub.vip_group_id = vip_id; await s.commit()
        await q.message.reply_text('✅ Groupe VIP associé.', reply_markup=group_manage_keyboard(pub_id, 'pub'))
    elif data.startswith('a:recheck:'):
        gid = int(data.split(':')[2])
        ok, detail = await bot_admin_check(context, gid)
        async with SessionLocal() as s:
            g = await s.get(Group, gid)
        if not g:
            await q.message.reply_text('Groupe introuvable.'); return
        if ok:
            await q.message.reply_text(
                f'✅ <b>{g.title}</b>\n\nLe bot est bien administrateur et peut gérer les liens d’invitation.\nChoisis maintenant le rôle du groupe :',
                parse_mode=ParseMode.HTML, reply_markup=group_role_keyboard(gid))
        else:
            await q.message.reply_text(
                f'❌ <b>Configuration impossible</b>\n\n{g.title}\n{detail}.\n\nPromue le bot administrateur avec le droit d’inviter des utilisateurs, puis appuie sur « Vérifier à nouveau ».',
                parse_mode=ParseMode.HTML, reply_markup=promote_required_keyboard(gid))
    elif data.startswith('a:role:'):
        _, _, gid_s, role_s = data.split(':'); gid = int(gid_s); role = GroupRole(role_s)
        if role != GroupRole.blocked:
            ok, detail = await bot_admin_check(context, gid)
            if not ok:
                await q.message.reply_text(
                    f'❌ Impossible d’enregistrer ce groupe : {detail}.\n\nPromue le bot administrateur avec le droit d’inviter des utilisateurs.',
                    reply_markup=promote_required_keyboard(gid))
                return
        async with SessionLocal() as s:
            g = await s.get(Group, gid)
            if not g:
                await q.message.reply_text('Groupe introuvable.'); return
            g.role = role; g.authorized = role != GroupRole.blocked; await s.commit()
        await q.message.reply_text(f'✅ Groupe configuré comme {role.value}.', reply_markup=admin_menu())
    elif data == 'a:proofs':
        async with SessionLocal() as s:
            proofs = (await s.scalars(select(Proof).where(Proof.status == ProofStatus.pending).order_by(Proof.created_at).limit(10))).all()
            for p in proofs:
                c = await s.get(Campaign, p.campaign_id)
                await q.message.reply_photo(p.file_id, caption=f'Preuve #{p.id}\nUtilisateur : {c.user_id}\nCampagne : {c.id}', reply_markup=proof_review_keyboard(p.id))
        if not proofs: await q.message.reply_text('Aucune preuve en attente.')
    elif data.startswith('a:proof:'):
        _, _, pid_s, action = data.split(':'); pid = int(pid_s)
        async with SessionLocal() as s:
            p = await s.get(Proof, pid)
            if not p or p.status != ProofStatus.pending: await q.message.reply_text('Déjà traitée.'); return
            c = await s.get(Campaign, p.campaign_id)
            p.reviewer_id = q.from_user.id; p.reviewed_at = now()
            if action == 'approve': p.status = ProofStatus.approved; c.status = CampaignStatus.active
            elif action == 'reject': p.status = ProofStatus.rejected; c.status = CampaignStatus.awaiting_proof; p.rejection_reason = 'Preuve non conforme'
            else: p.status = ProofStatus.rejected; c.status = CampaignStatus.banned; c.active_slot = None; user = await s.get(User, c.user_id); user.is_banned = True
            await s.commit()
        if action == 'approve': await context.bot.send_message(c.user_id, f'✅ Ta publication a été validée ! Ton compteur est activé. Objectif : {settings.invite_goal}.', reply_markup=user_menu())
        elif action == 'reject': await context.bot.send_message(c.user_id, '❌ Ta capture n’a pas pu être validée. Envoie une nouvelle capture complète.', reply_markup=proof_menu())
        else: await context.bot.send_message(c.user_id, '🚫 Ton accès au parcours a été suspendu.')
        await q.message.reply_text('✅ Action enregistrée.')
    elif data == 'a:stats':
        async with SessionLocal() as s:
            users = await s.scalar(select(func.count()).select_from(User)); campaigns = await s.scalar(select(func.count()).select_from(Campaign)); valid = await s.scalar(select(func.sum(Campaign.valid_count))) or 0
        await q.message.reply_text(f'📊 Utilisateurs : {users}\nCampagnes : {campaigns}\nInvitations validées : {valid}')
    elif data == 'a:post_ads':
        sent = 0
        me = await context.bot.get_me()
        async with SessionLocal() as s:
            groups = (await s.scalars(select(Group).where(Group.role == GroupRole.pub, Group.authorized.is_(True)))).all()
        for g in groups:
            url = f'https://t.me/{me.username}?start=pub_{g.source_token}'
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('🎁 VIP GRATUIT', url=url)]])
            try:
                if g.ad_photo_file_id: await context.bot.send_photo(g.chat_id, g.ad_photo_file_id, caption=g.ad_text or 'Débloque ton VIP gratuit.', reply_markup=kb)
                else: await context.bot.send_message(g.chat_id, g.ad_text or 'Débloque ton VIP gratuit.', reply_markup=kb)
                sent += 1
            except TelegramError as exc: log.warning('Pub impossible dans %s: %s', g.chat_id, exc)
        await q.message.reply_text(f'📢 Publication envoyée dans {sent} groupe(s).')


async def admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or update.effective_chat.type != ChatType.PRIVATE or not update.message.text:
        return
    if not await is_admin(update.effective_user.id):
        return
    pending = context.user_data.get('admin_input')
    if not pending:
        return
    if update.message.text.strip().lower() == '/annuler':
        context.user_data.pop('admin_input', None)
        await update.message.reply_text('Configuration annulée.', reply_markup=admin_menu())
        return
    if pending['kind'] not in ('ad_text', 'private_text'):
        await update.message.reply_text('Une image est attendue, pas un texte.')
        return
    async with SessionLocal() as s:
        g = await s.get(Group, pending['group_id'])
        if not g:
            await update.message.reply_text('Groupe introuvable.'); context.user_data.pop('admin_input', None); return
        if pending['kind'] == 'ad_text': g.ad_text = update.message.text
        else: g.private_intro = update.message.text
        await s.commit()
    context.user_data.pop('admin_input', None)
    await update.message.reply_text('✅ Texte enregistré.', reply_markup=group_manage_keyboard(g.chat_id, g.role.value))


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or update.effective_chat.type != ChatType.PRIVATE or not update.message.photo:
        return
    if await is_admin(update.effective_user.id):
        pending = context.user_data.get('admin_input')
        if pending and pending.get('kind') in ('ad_photo', 'private_photo'):
            async with SessionLocal() as s:
                g = await s.get(Group, pending['group_id'])
                if not g:
                    await update.message.reply_text('Groupe introuvable.'); context.user_data.pop('admin_input', None); return
                if pending['kind'] == 'ad_photo': g.ad_photo_file_id = update.message.photo[-1].file_id
                else: g.private_photo_file_id = update.message.photo[-1].file_id
                await s.commit()
            context.user_data.pop('admin_input', None)
            await update.message.reply_text('✅ Image enregistrée.', reply_markup=group_manage_keyboard(g.chat_id, g.role.value))
            return
        if (update.message.caption or '').startswith(('#ad ', '#private ')):
            await admin_photo_config(update, context); return
    camp = await active_campaign(update.effective_user.id)
    if not camp or camp.status not in (CampaignStatus.awaiting_proof, CampaignStatus.proof_review):
        await update.message.reply_text('Aucune preuve attendue.'); return
    async with SessionLocal() as s:
        c = await s.get(Campaign, camp.id); c.status = CampaignStatus.proof_review
        proof = Proof(campaign_id=c.id, file_id=update.message.photo[-1].file_id)
        s.add(proof); await s.commit(); await s.refresh(proof)
    await update.message.reply_text('📸 Capture bien reçue ! Ta preuve est en cours de vérification.', reply_markup=user_menu())
    for aid in settings.owner_ids:
        try: await context.bot.send_photo(aid, proof.file_id, caption=f'📸 Nouvelle preuve #{proof.id}\nUtilisateur : {camp.user_id}\nCampagne : {camp.id}', reply_markup=proof_review_keyboard(proof.id))
        except TelegramError: pass


async def my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmu = update.my_chat_member
    if not cmu: return
    new_status = cmu.new_chat_member.status
    if new_status not in (ChatMember.ADMINISTRATOR, ChatMember.MEMBER): return
    chat = cmu.chat; actor = cmu.from_user
    token = secrets.token_urlsafe(8).replace('-', '').replace('_', '')[:12]
    authorized_actor = await is_admin(actor.id)
    async with SessionLocal() as s:
        g = await s.get(Group, chat.id)
        if not g:
            g = Group(chat_id=chat.id, title=chat.title or str(chat.id), source_token=token, authorized=False)
            s.add(g)
        else: g.title = chat.title or g.title
        await s.commit()
    if authorized_actor:
        # Detect group admins as panel admins, but only after an authorized connection.
        try:
            admins = await context.bot.get_chat_administrators(chat.id)
            newly_detected = []
            async with SessionLocal() as s:
                for member in admins:
                    if member.user.is_bot:
                        continue
                    if not await s.get(Admin, member.user.id):
                        s.add(Admin(telegram_id=member.user.id, source='group_admin'))
                        newly_detected.append(member.user.id)
                await s.commit()
            # Telegram n'autorise un bot à écrire en privé qu'après que la personne
            # a démarré le bot. On tente tout de même d'afficher automatiquement le panneau.
            for admin_id in newly_detected:
                try:
                    await context.bot.send_message(
                        admin_id,
                        '🛠 Ton compte administrateur a été détecté automatiquement.',
                        reply_markup=admin_menu(),
                    )
                except TelegramError:
                    pass
        except TelegramError: pass
        admin_ok, detail = await bot_admin_check(context, chat.id)
        for oid in settings.owner_ids:
            try:
                if admin_ok:
                    await context.bot.send_message(
                        oid, f'✅ <b>Nouveau groupe détecté</b>\n\nNom : {chat.title}\nID : <code>{chat.id}</code>\nBot administrateur : 🟢 Oui\n\nQuel est son rôle ?',
                        parse_mode=ParseMode.HTML, reply_markup=group_role_keyboard(chat.id))
                else:
                    await context.bot.send_message(
                        oid, f'❌ <b>Configuration impossible</b>\n\nNom : {chat.title}\nID : <code>{chat.id}</code>\nÉtat : {detail}\n\nPromue le bot administrateur avec le droit d’inviter des utilisateurs, puis vérifie à nouveau.',
                        parse_mode=ParseMode.HTML, reply_markup=promote_required_keyboard(chat.id))
            except TelegramError:
                pass
    else:
        for oid in settings.owner_ids:
            try: await context.bot.send_message(oid, f'🚨 Tentative de raccordement non autorisée\nGroupe : {chat.title}\nID : <code>{chat.id}</code>\nAjouté par : {actor.id}', parse_mode=ParseMode.HTML)
            except TelegramError: pass
        try: await context.bot.send_message(chat.id, '⚠️ Ce groupe n’est pas autorisé à utiliser ce bot. Le bot va quitter ce groupe.'); await context.bot.leave_chat(chat.id)
        except TelegramError: pass


async def chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmu = update.chat_member
    if not cmu or not cmu.invite_link: return
    old = cmu.old_chat_member.status; new = cmu.new_chat_member.status
    if old in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER) or new not in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR): return
    link = cmu.invite_link.invite_link
    async with SessionLocal() as s:
        camp = await s.scalar(select(Campaign).where(Campaign.invite_link == link, Campaign.status.in_((CampaignStatus.active, CampaignStatus.vip_active))))
        if not camp or cmu.new_chat_member.user.id == camp.user_id: return
        exists = await s.scalar(select(Invite).where(Invite.campaign_id == camp.id, Invite.joined_user_id == cmu.new_chat_member.user.id))
        if exists: return
        inv = Invite(campaign_id=camp.id, joined_user_id=cmu.new_chat_member.user.id, validate_after=now() + timedelta(minutes=settings.join_validation_minutes))
        s.add(inv); camp.pending_count += 1
        try: await s.commit()
        except IntegrityError: await s.rollback()


async def validate_invites(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with SessionLocal() as s:
        invites = (await s.scalars(select(Invite).where(Invite.status == InviteStatus.pending, Invite.validate_after <= now()).limit(100))).all()
        for inv in invites:
            camp = await s.get(Campaign, inv.campaign_id)
            try:
                member = await context.bot.get_chat_member(camp.pub_group_id, inv.joined_user_id)
                valid = member.status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER, ChatMember.RESTRICTED)
            except TelegramError:
                valid = False
            camp.pending_count = max(0, camp.pending_count - 1); inv.validated_at = now()
            if valid:
                inv.status = InviteStatus.valid; camp.valid_count += 1; camp.last_valid_at = now(); camp.stagnation_notice_at = None
                await maybe_credit_vip(context, s, camp)
                try: await context.bot.send_message(camp.user_id, f'🎉 Une nouvelle invitation vient d’être validée !\nProgression : {camp.valid_count}')
                except TelegramError: pass
            else:
                inv.status = InviteStatus.invalid; camp.invalid_count += 1
                try: await context.bot.send_message(camp.user_id, 'Invitation non validée. La personne n’a pas rejoint le groupe ou ne respecte pas les conditions.')
                except TelegramError: pass
        await s.commit()


async def maybe_credit_vip(context, session, camp: Campaign) -> None:
    goals = camp.valid_count // settings.invite_goal
    if goals <= camp.credited_goals: return
    new_goals = goals - camp.credited_goals
    base = max(camp.vip_expires_at or now(), now())
    camp.vip_expires_at = base + timedelta(days=settings.vip_days_per_goal * new_goals)
    camp.credited_goals = goals
    if not camp.vip_started_at: camp.vip_started_at = now()
    camp.status = CampaignStatus.vip_active
    expire_link = now() + timedelta(hours=settings.vip_link_ttl_hours)
    try:
        vip_link = await context.bot.create_chat_invite_link(camp.vip_group_id, expire_date=expire_link, member_limit=1, name=f'vip{camp.user_id}'[:32])
        kb = InlineKeyboardMarkup([[InlineKeyboardButton('🔐 REJOINDRE LE VIP', url=vip_link.invite_link)]])
        await context.bot.send_message(camp.user_id,
            f'🎉 Félicitations ! Tu as atteint {goals * settings.invite_goal} invitations validées.\n'
            f'{settings.vip_days_per_goal * new_goals} jours ont été crédités.\n'
            f'Le bouton d’entrée est valable {settings.vip_link_ttl_hours} heures.\n\n'
            'Après cette réussite, tu peux aussi partager ton lien sur Reddit, Discord ou TikTok lorsque leurs règles l’autorisent.', reply_markup=kb)
    except TelegramError as exc:
        log.exception('Impossible de créer le lien VIP: %s', exc)


async def maintenance(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with SessionLocal() as s:
        camps = (await s.scalars(select(Campaign).where(Campaign.status.in_((CampaignStatus.active, CampaignStatus.vip_active))))).all()
        for c in camps:
            # Stagnation: >0, below next goal, no valid invite for configured hours.
            reference = c.last_valid_at or c.created_at
            if c.valid_count > 0 and c.valid_count % settings.invite_goal != 0 and reference <= now() - timedelta(hours=settings.stagnation_hours) and not c.stagnation_notice_at:
                try:
                    await context.bot.send_message(c.user_id,
                        f'💡 Ta progression semble s’être arrêtée à {c.valid_count}.\n\n'
                        'Exceptionnellement, tu peux partager ce lien direct, sans espace, sur Telegram, Discord ou TikTok lorsque le règlement l’autorise :\n\n'
                        f'{c.invite_link}\n\nPour Leakimedia, continue à utiliser uniquement le texte avec les espaces.')
                    c.stagnation_notice_at = now()
                except TelegramError: pass
            if c.status == CampaignStatus.vip_active and c.vip_expires_at:
                remaining = c.vip_expires_at - now()
                for days in settings.reminder_days:
                    if timedelta(days=days-1) < remaining <= timedelta(days=days):
                        ref = c.vip_expires_at.date().isoformat(); key = f'expire_{days}'
                        exists = await s.scalar(select(Reminder).where(Reminder.campaign_id == c.id, Reminder.kind == key, Reminder.reference_date == ref))
                        if not exists:
                            try: await context.bot.send_message(c.user_id, f'⏳ Ton accès VIP expire dans environ {days} jour(s), le {c.vip_expires_at.strftime("%d/%m/%Y à %H:%M")}. Continue à partager pour créditer de nouvelles périodes de {settings.vip_days_per_goal} jours.')
                            except TelegramError: pass
                            s.add(Reminder(campaign_id=c.id, kind=key, reference_date=ref))
                if c.vip_expires_at <= now():
                    try:
                        await context.bot.ban_chat_member(c.vip_group_id, c.user_id, until_date=now() + timedelta(seconds=60))
                        await context.bot.unban_chat_member(c.vip_group_id, c.user_id, only_if_banned=True)
                    except TelegramError as exc: log.warning('Retrait VIP impossible: %s', exc)
                    c.status = CampaignStatus.expired; c.active_slot = None
                    try: await context.bot.send_message(c.user_id, '⌛ Ton accès VIP est arrivé à expiration. Tu as été retiré du groupe VIP. Tu peux recommencer une nouvelle campagne.')
                    except TelegramError: pass
        await s.commit()


async def post_init(app: Application) -> None:
    await init_db()
    async with SessionLocal() as s:
        for oid in settings.owner_ids:
            if not await s.get(Admin, oid): s.add(Admin(telegram_id=oid, source='owner'))
        await s.commit()
    app.job_queue.run_repeating(validate_invites, interval=60, first=15, name='validate_invites')
    app.job_queue.run_repeating(maintenance, interval=3600, first=30, name='maintenance')


def build_app() -> Application:
    app = Application.builder().token(settings.bot_token).post_init(post_init).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin_cmd))
    app.add_handler(CommandHandler(['setad', 'setintro', 'linkvip'], configure_cmd))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_input))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(ChatMemberHandler(my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(chat_member, ChatMemberHandler.CHAT_MEMBER))
    return app


def main() -> None:
    build_app().run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)


if __name__ == '__main__':
    main()
