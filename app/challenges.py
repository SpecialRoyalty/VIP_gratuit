"""Défi facultatif et droits VIP permanents, distincts des minutes et des rangs."""
from __future__ import annotations

import asyncio
from datetime import timedelta, timezone
from html import escape
from weakref import WeakValueDictionary

from sqlalchemy import func, select
from telegram import InlineKeyboardButton as Button, InlineKeyboardMarkup as Markup
from telegram.constants import ParseMode
from telegram.error import TelegramError

from .config import settings
from .db import SessionLocal
from .models import (Admin, Campaign, CampaignStatus, ChallengeEnrollment, ChallengeEvidence,
                     Group, GroupRole, Invite, InviteStatus, LifetimeAccess,
                     TrialAccess, TrialStatus, User, VipSession, VipSessionStatus)
from .services import active_campaign, is_admin, now
from .ranks import progress_bar

TARGET = 200
_access_locks = WeakValueDictionary()


def access_lock(user_id: int) -> asyncio.Lock:
    lock = _access_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _access_locks[user_id] = lock
    return lock


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def keyboard(rows):
    return Markup([[Button(label, callback_data=data) for label, data in row] for row in rows])


def home_row():
    return [('⬅️ MON ESPACE', 'u:counter')]


async def lifetime_grant(db, user_id: int, chat_id: int):
    return await db.scalar(select(LifetimeAccess).join(User, User.telegram_id == LifetimeAccess.user_id).where(
        LifetimeAccess.user_id == user_id, LifetimeAccess.vip_group_id == chat_id,
        LifetimeAccess.active.is_(True), User.banned.is_(False),
    ))


async def has_lifetime(user_id: int, chat_id: int) -> bool:
    async with SessionLocal() as db:
        return await lifetime_grant(db, user_id, chat_id) is not None


async def all_lifetime(user_id: int):
    async with SessionLocal() as db:
        return list((await db.scalars(select(LifetimeAccess).join(User).where(
            LifetimeAccess.user_id == user_id, LifetimeAccess.active.is_(True), User.banned.is_(False),
        ).order_by(LifetimeAccess.id))).all())


async def progress(db, enrollment) -> tuple[int, int]:
    # Une arrivée antérieure à l'inscription ne compte pas, même validée ensuite.
    conditions = (Invite.campaign_id == enrollment.campaign_id, Invite.joined_at >= enrollment.joined_at)
    valid = int(await db.scalar(select(func.count(Invite.id)).where(*conditions, Invite.status == InviteStatus.valid)) or 0)
    pending = int(await db.scalar(select(func.count(Invite.id)).where(*conditions, Invite.status == InviteStatus.pending)) or 0)
    return valid, pending


async def evidence_count(db, enrollment_id):
    return int(await db.scalar(select(func.count(ChallengeEvidence.id)).where(
        ChallengeEvidence.enrollment_id == enrollment_id)) or 0)


async def enrollment_for(db, campaign_id):
    return await db.scalar(select(ChallengeEnrollment).where(ChallengeEnrollment.campaign_id == campaign_id))


async def show_challenge(message, user_id):
    camp = await active_campaign(user_id)
    if not camp:
        await message.reply_text('Ouvre « VIP GRATUIT » depuis un groupe partenaire pour participer.', reply_markup=keyboard([home_row()]))
        return
    async with SessionLocal() as db:
        enrollment = await enrollment_for(db, camp.id)
        permanent = await lifetime_grant(db, user_id, camp.vip_group_id)
        valid, pending = await progress(db, enrollment) if enrollment else (0, 0)
        proofs = await evidence_count(db, enrollment.id) if enrollment else 0
    if permanent:
        await message.reply_text('👑 <b>Ton accès VIP à vie est actif.</b>\n\nUn administrateur a validé ta demande.',
                                 parse_mode=ParseMode.HTML,
                                 reply_markup=keyboard([[('🔐 ACCÉDER AU VIP', f'u:lifetime:{permanent.id}')], home_row()]))
        return
    if not enrollment:
        await message.reply_text(
            '🏆 <b>Défi VIP à vie — facultatif</b>\n\n'
            f'Invite <b>{TARGET} nouvelles personnes éligibles venant de Leakmedia ou Discord</b>.\n\n'
            '✅ Seules les invitations validées après ton inscription, avec une arrivée après celle-ci, comptent.\n'
            f'⏳ Chaque invité doit rester au moins {settings.validation_minutes} minute(s).\n'
            '🔗 Tu conserves ton lien permanent. Tes minutes et ton rang continuent à progresser.\n\n'
            '🛡 Un administrateur vérifie les invitations et leur provenance avant d’accorder l’accès à vie '
            'au VIP associé. Tu peux joindre des justificatifs. Atteindre 200 ne donne pas automatiquement accès.\n\n'
            'Tu peux continuer à utiliser le bot sans participer.',
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard([[('🚀 JE PARTICIPE', 'u:challenge:join')], home_row()]),
        )
        return
    text = (f'🏆 <b>Mon défi VIP à vie</b>\n\n'
            f'<b>{valid} / {TARGET} invitations validées</b>\n'
            f'{progress_bar(valid, TARGET)} {min(100, valid*100//TARGET)} %\n\n'
            f'⏳ En vérification : {pending}\n'
            f'🎯 Encore {max(0, TARGET-valid)} invitation(s)\n'
            f'📎 Justificatifs enregistrés : {proofs}\n\n')
    rows = [[('🔗 MON LIEN', 'u:link')]]
    if enrollment.status == 'pending':
        text += '⏳ <b>Demande en attente de validation administrateur.</b>\nTu seras prévenu de la décision.'
    elif enrollment.status == 'rejected':
        text += f'❌ <b>Demande refusée</b>\nMotif : {escape(enrollment.review_reason or "Non précisé")}\n\nAjoute de nouveaux justificatifs pour demander un nouvel examen.'
    else:
        text += 'La provenance Leakmedia / Discord reste à vérifier par un administrateur.'
    if enrollment.status in ('enrolled', 'pending', 'rejected'):
        rows.append([('📎 AJOUTER UN JUSTIFICATIF', 'u:challenge:proof')])
    if valid >= TARGET and enrollment.status in ('enrolled', 'rejected'):
        rows.append([('📩 DEMANDER MON ACCÈS À VIE', 'u:challenge:submit')])
    rows += [[('🔄 ACTUALISER', 'u:challenge')], home_row()]
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard(rows))


async def enroll(user_id):
    async with access_lock(user_id):
        camp = await active_campaign(user_id)
        if not camp:
            return 'Aucune campagne active.'
        async with SessionLocal() as db:
            user = await db.get(User, user_id)
            group = await db.get(Group, camp.pub_group_id)
            if not user or user.banned or not group or group.role != GroupRole.pub or not group.authorized:
                return 'Inscription indisponible pour ce groupe.'
            if await lifetime_grant(db, user_id, camp.vip_group_id):
                return 'Tu possèdes déjà un accès à vie à ce VIP.'
            if not await enrollment_for(db, camp.id):
                db.add(ChallengeEnrollment(user_id=user_id, campaign_id=camp.id,
                                           vip_group_id=camp.vip_group_id, joined_at=now()))
                await db.commit()
    return None


async def review_text(db, enrollment):
    valid, pending = await progress(db, enrollment)
    camp = await db.get(Campaign, enrollment.campaign_id)
    group = await db.get(Group, camp.pub_group_id) if camp else None
    user = await db.get(User, enrollment.user_id)
    proofs = await evidence_count(db, enrollment.id)
    return (f'🏆 <b>Demande VIP à vie #{enrollment.id}</b> — examen {enrollment.submission_no}\n\n'
            f'Utilisateur : <code>{enrollment.user_id}</code> (@{escape(user.username or "sans_pseudo") if user else "inconnu"})\n'
            f'Groupe PUB : {escape(group.title) if group else "indisponible"}\n'
            f'VIP : <code>{enrollment.vip_group_id}</code>\n'
            f'Invitations validées depuis inscription : <b>{valid} / {TARGET}</b>\n'
            f'En vérification : {pending}\nJustificatifs : {proofs}\n'
            f'Statut : {escape(enrollment.status)}\n\n'
            'La provenance Leakmedia / Discord nécessite votre vérification. Aucun accès automatique.')


def review_keyboard(enrollment, proof_after=0):
    token = f'{enrollment.id}:{enrollment.submission_no}'
    rows = [[('📎 JUSTIFICATIFS', f'a:ch:proofs:{enrollment.id}:{proof_after}')]]
    if enrollment.status == 'pending':
        rows += [[('✅ APPROUVER', f'a:ch:approve:{token}'), ('❌ REFUSER', f'a:ch:reject:{token}')]]
    rows.append([('⬅️ DEMANDES EN ATTENTE', 'a:ch:queue:0')])
    return keyboard(rows)


async def notify_review(bot, enrollment_id):
    async with SessionLocal() as db:
        enrollment = await db.get(ChallengeEnrollment, enrollment_id)
        text = await review_text(db, enrollment)
        markup = review_keyboard(enrollment)
        ids = set(settings.owner_ids) | set((await db.scalars(select(Admin.telegram_id).where(Admin.active.is_(True)))).all())
    for uid in ids:
        try:
            await bot.send_message(uid, text, parse_mode=ParseMode.HTML, reply_markup=markup)
        except TelegramError:
            pass  # La demande reste accessible dans la file persistante des administrateurs.


async def submit(user_id):
    async with access_lock(user_id):
        camp = await active_campaign(user_id)
        if not camp:
            return None, 'Aucune campagne active.'
        async with SessionLocal() as db:
            enrollment = await enrollment_for(db, camp.id)
            if not enrollment:
                return None, 'Inscris-toi d’abord au défi.'
            if enrollment.status not in ('enrolled', 'rejected'):
                return None, 'Une demande est déjà en cours ou a été traitée.'
            valid, _ = await progress(db, enrollment)
            if valid < TARGET:
                return None, f'Il faut {TARGET} invitations validées après inscription.'
            proofs = await evidence_count(db, enrollment.id)
            if enrollment.status == 'rejected' and proofs <= enrollment.submitted_evidence_count:
                return None, 'Ajoute de nouveaux justificatifs avant de demander un nouvel examen.'
            enrollment.status = 'pending'
            enrollment.submission_no += 1
            enrollment.submitted_evidence_count = proofs
            enrollment.submitted_at = now()
            await db.commit()
            return enrollment.id, None


async def decide(enrollment_id, revision, admin_id, *, approve=False, reason=None):
    if not await is_admin(admin_id):
        return None, 'Accès refusé.'
    async with SessionLocal() as db:
        found = await db.get(ChallengeEnrollment, enrollment_id)
        if not found:
            return None, 'Demande introuvable.'
        uid = found.user_id
    async with access_lock(uid):
        async with SessionLocal() as db:
            # Le verrou DB protège aussi une double décision admin.
            enrollment = await db.scalar(select(ChallengeEnrollment).where(
                ChallengeEnrollment.id == enrollment_id).with_for_update())
            if enrollment.status != 'pending' or enrollment.submission_no != revision:
                return None, 'Cette demande a déjà été traitée ou ce bouton est ancien.'
            camp = await db.get(Campaign, enrollment.campaign_id)
            user = await db.get(User, uid)
            if approve:
                valid, _ = await progress(db, enrollment)
                vip = await db.get(Group, enrollment.vip_group_id)
                if (not camp or camp.status != CampaignStatus.active or not user or user.banned or
                        not vip or vip.role != GroupRole.vip or not vip.authorized or valid < TARGET):
                    return None, 'Approbation impossible : campagne, utilisateur, VIP ou invitations non éligibles.'
                grant = await db.scalar(select(LifetimeAccess).where(
                    LifetimeAccess.user_id == uid, LifetimeAccess.vip_group_id == enrollment.vip_group_id))
                if not grant:
                    db.add(LifetimeAccess(user_id=uid, vip_group_id=enrollment.vip_group_id,
                                          enrollment_id=enrollment.id, granted_by=admin_id))
                else:
                    grant.active = True
                    grant.granted_by = admin_id
                    grant.granted_at = now()
                for model, statuses, cancelled in (
                    (TrialAccess, [TrialStatus.active, TrialStatus.kick_pending, TrialStatus.link_created], TrialStatus.cancelled),
                    (VipSession, [VipSessionStatus.active, VipSessionStatus.kick_pending, VipSessionStatus.link_created], VipSessionStatus.cancelled),
                ):
                    rows = list((await db.scalars(select(model).where(
                        model.user_id == uid, model.vip_group_id == enrollment.vip_group_id,
                        model.status.in_(statuses)))).all())
                    for row in rows:
                        row.status = cancelled
                        row.last_kick_error = None
                enrollment.status = 'approved'
            else:
                if not reason or not reason.strip():
                    return None, 'Un motif de refus est obligatoire.'
                enrollment.status = 'rejected'
                # Un nouvel examen nécessitera une pièce ajoutée après cette décision.
                enrollment.submitted_evidence_count = await evidence_count(db, enrollment.id)
            enrollment.review_reason = reason
            enrollment.reviewed_at = now()
            enrollment.reviewed_by = admin_id
            await db.commit()
            return uid, None


async def show_lifetime_accesses(message, user_id):
    grants = await all_lifetime(user_id)
    async with SessionLocal() as db:
        rows = []
        for grant in grants:
            group = await db.get(Group, grant.vip_group_id)
            rows.append([(f'🔐 {group.title if group else "VIP"}', f'u:lifetime:{grant.id}')])
    await message.reply_text('👑 Tes accès VIP à vie' if grants else 'Aucun accès à vie validé pour le moment.',
                             reply_markup=keyboard(rows + [home_row()]))


async def send_lifetime_link(message, bot, user_id, grant_id):
    async with access_lock(user_id):
        async with SessionLocal() as db:
            grant = await db.get(LifetimeAccess, grant_id)
            if not grant or grant.user_id != user_id or not await lifetime_grant(db, user_id, grant.vip_group_id):
                await message.reply_text('Accès à vie indisponible.'); return
            group = await db.get(Group, grant.vip_group_id)
            if not group or group.role != GroupRole.vip or not group.authorized:
                await message.reply_text('Ce VIP est actuellement indisponible.'); return
            link = grant.invite_link
            if not link or not grant.invite_expires_at or aware(grant.invite_expires_at) <= now():
                expiry = now() + timedelta(minutes=settings.vip_link_ttl_minutes)
                try:
                    created = await bot.create_chat_invite_link(grant.vip_group_id,
                        name=f'permanent-{user_id}'[:32], expire_date=expiry, member_limit=1)
                except TelegramError:
                    await message.reply_text('Impossible de préparer l’entrée maintenant. Ton accès à vie reste acquis.'); return
                link = grant.invite_link = created.invite_link
                grant.invite_expires_at = expiry
                await db.commit()
        await message.reply_text(
            '👑 Ton droit d’accès est permanent. Ce lien personnel sert à entrer dans le VIP '
            f'et reste utilisable {settings.vip_link_ttl_minutes} minutes après sa création. '
            'Tu pourras en demander un autre ici si nécessaire.',
            reply_markup=Markup([[Button('🔐 REJOINDRE LE VIP', url=link)]]))


async def handle_user_callback(q, context, data):
    uid = q.from_user.id
    if data == 'u:challenge:cancelinput':
        context.user_data.pop('challenge_proof', None)
        await show_challenge(q.message, uid)
    elif data == 'u:challenge':
        context.user_data.pop('challenge_proof', None)
        await show_challenge(q.message, uid)
    elif data == 'u:challenge:join':
        error = await enroll(uid)
        if error: await q.message.reply_text(error)
        else: await show_challenge(q.message, uid)
    elif data == 'u:challenge:submit':
        eid, error = await submit(uid)
        if error: await q.message.reply_text(error)
        else:
            await show_challenge(q.message, uid)
            await notify_review(context.bot, eid)
    elif data == 'u:challenge:proof':
        camp = await active_campaign(uid)
        async with SessionLocal() as db:
            enrollment = await enrollment_for(db, camp.id) if camp else None
        if not enrollment or enrollment.status not in ('enrolled', 'pending', 'rejected'):
            await q.message.reply_text('Inscris-toi au défi avant d’ajouter un justificatif.'); return True
        context.user_data['challenge_proof'] = enrollment.id
        await q.message.reply_text('Envoie un texte ou une capture justifiant la provenance de tes invités. '
                                  'Cette pièce sera consultable par les administrateurs.',
                                  reply_markup=keyboard([[('❌ ANNULER', 'u:challenge:cancelinput')]]))
    elif data == 'u:lifetime':
        await show_lifetime_accesses(q.message, uid)
    elif data.startswith('u:lifetime:'):
        try: grant_id = int(data.rsplit(':', 1)[1])
        except ValueError: return True
        await send_lifetime_link(q.message, context.bot, uid, grant_id)
    else:
        return False
    return True


async def handle_admin_callback(q, context, data):
    if not data.startswith('a:ch:'):
        return False
    if not await is_admin(q.from_user.id):
        await q.message.reply_text('Accès refusé.'); return True
    parts = data.split(':')
    action = parts[2]
    if action == 'cancel':
        context.user_data.pop('challenge_reject', None)
        await q.message.reply_text('Action annulée.'); return True
    try: ident = int(parts[3])
    except (ValueError, IndexError): return True
    if action == 'queue':
        async with SessionLocal() as db:
            rows = list((await db.scalars(select(ChallengeEnrollment).where(
                ChallengeEnrollment.status == 'pending', ChallengeEnrollment.id > ident,
            ).order_by(ChallengeEnrollment.id).limit(11))).all())
        buttons = [[(f'📋 Demande #{r.id} · {r.user_id}', f'a:ch:view:{r.id}')] for r in rows[:10]]
        if len(rows) > 10: buttons.append([('SUIVANTES →', f'a:ch:queue:{rows[9].id}')])
        buttons.append([('⬅️ MENU ADMIN', 'a:menu')])
        await q.message.reply_text('🏆 Demandes VIP à vie en attente' if rows else 'Aucune demande en attente.', reply_markup=keyboard(buttons))
        return True
    async with SessionLocal() as db:
        enrollment = await db.get(ChallengeEnrollment, ident)
        if not enrollment:
            await q.message.reply_text('Demande introuvable.'); return True
        text = await review_text(db, enrollment)
        if action == 'proofs':
            try: after = int(parts[4])
            except (ValueError, IndexError): after = 0
            proofs = list((await db.scalars(select(ChallengeEvidence).where(
                ChallengeEvidence.enrollment_id == ident, ChallengeEvidence.id > after,
            ).order_by(ChallengeEvidence.id).limit(6))).all())
        else:
            proofs = []
    if action == 'view':
        await q.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=review_keyboard(enrollment))
    elif action == 'proofs':
        for proof in proofs[:5]:
            if proof.photo_file_id:
                try: await context.bot.send_photo(q.from_user.id, proof.photo_file_id, caption=f'Justificatif #{proof.id}')
                except TelegramError: await q.message.reply_text(f'Photo #{proof.id} indisponible.')
            if proof.text: await q.message.reply_text(f'Justificatif #{proof.id}\n{proof.text}')
        rows = [[('⬅️ DOSSIER', f'a:ch:view:{ident}')]]
        if len(proofs) > 5: rows.insert(0, [('SUIVANTS →', f'a:ch:proofs:{ident}:{proofs[4].id}')])
        await q.message.reply_text('Justificatifs du dossier' if proofs else 'Aucun justificatif enregistré.', reply_markup=keyboard(rows))
    elif action in ('approve', 'confirm', 'reject'):
        try: revision = int(parts[4])
        except (ValueError, IndexError): return True
        if enrollment.status != 'pending' or revision != enrollment.submission_no:
            await q.message.reply_text('Ce bouton est ancien ou la demande a déjà été traitée.'); return True
        if action == 'approve':
            await q.message.reply_text(text + '\n\n<b>Confirmez avoir vérifié la provenance des invités et vouloir accorder un accès VIP à vie.</b>',
                parse_mode=ParseMode.HTML, reply_markup=keyboard([
                    [('✅ PROVENANCE VÉRIFIÉE — ACCORDER À VIE', f'a:ch:confirm:{ident}:{revision}')],
                    [('❌ ANNULER', f'a:ch:view:{ident}')]]))
        elif action == 'reject':
            context.user_data['challenge_reject'] = (ident, revision)
            await q.message.reply_text('Envoie le motif du refus. Il sera communiqué à l’utilisateur.',
                reply_markup=keyboard([[('❌ ANNULER', 'a:ch:cancel')]]))
        else:
            uid, error = await decide(ident, revision, q.from_user.id, approve=True)
            if error: await q.message.reply_text(error)
            else:
                await q.message.reply_text('✅ Accès à vie accordé et enregistré.')
                try:
                    await context.bot.send_message(uid, '👑 Ton accès VIP à vie a été approuvé par un administrateur !',
                        reply_markup=keyboard([[('🔐 MES ACCÈS VIP À VIE', 'u:lifetime')]]))
                except TelegramError:
                    await q.message.reply_text('Le message privé n’a pas pu être remis. Le droit reste actif et visible dans le bot.')
    return True


async def handle_input(update, context):
    uid = update.effective_user.id
    message = update.effective_message
    evidence_id = context.user_data.get('challenge_proof')
    rejection = context.user_data.get('challenge_reject')
    if evidence_id:
        async with access_lock(uid):
            async with SessionLocal() as db:
                enrollment = await db.get(ChallengeEnrollment, evidence_id)
                user = await db.get(User, uid)
                camp = await db.get(Campaign, enrollment.campaign_id) if enrollment else None
                if (not enrollment or enrollment.user_id != uid or not user or user.banned or
                        not camp or camp.status != CampaignStatus.active or
                        enrollment.status not in ('enrolled', 'pending', 'rejected')):
                    context.user_data.pop('challenge_proof', None)
                    await message.reply_text('Dossier indisponible.'); return True
                content = message.text or message.caption or ''
                if len(content) > 3000:
                    await message.reply_text('Limite : 3 000 caractères par justificatif.'); return True
                photo = message.photo[-1].file_id if message.photo else None
                if not content and not photo:
                    await message.reply_text('Envoie un texte ou une photo.'); return True
                db.add(ChallengeEvidence(enrollment_id=enrollment.id, text=content, photo_file_id=photo))
                await db.commit()
        context.user_data.pop('challenge_proof', None)
        await message.reply_text('✅ Justificatif enregistré.', reply_markup=keyboard([[('🏆 MON DÉFI', 'u:challenge')]]))
        return True
    if rejection and await is_admin(uid):
        reason = (message.text or '').strip()
        if not reason or len(reason) > 1500:
            await message.reply_text('Envoie un motif entre 1 et 1 500 caractères.'); return True
        target, error = await decide(*rejection, uid, reason=reason)
        context.user_data.pop('challenge_reject', None)
        if error: await message.reply_text(error)
        else:
            await message.reply_text('Refus enregistré.')
            try:
                await context.bot.send_message(target, f'❌ Ta demande VIP à vie n’a pas été validée.\n\nMotif : {reason}\n\n'
                    'Tu peux ajouter des justificatifs et demander un nouvel examen.',
                    reply_markup=keyboard([[('🏆 MON DÉFI', 'u:challenge')]]))
            except TelegramError:
                await message.reply_text('Message non remis ; le motif reste consultable dans le défi.')
        return True
    return False
