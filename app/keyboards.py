from urllib.parse import urlencode

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

REFERRAL_SAMPLE_SIZES = (5, 10, 20)


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🩺 SANTÉ', callback_data='a:health'), InlineKeyboardButton('📊 STATISTIQUES', callback_data='a:stats')],
        [InlineKeyboardButton('👥 GROUPES', callback_data='a:groups'), InlineKeyboardButton('🚫 MOTS INTERDITS', callback_data='a:words')],
        [InlineKeyboardButton('📣 BROADCAST PRIVÉ', callback_data='a:broadcast')],
        [InlineKeyboardButton('🏆 DEMANDES VIP À VIE', callback_data='a:ch:queue:0')],
        [InlineKeyboardButton('📬 BILAN ANNONCE', callback_data='a:notices')],
        [InlineKeyboardButton('🔗 VÉRIFIER LES LIENS RÉCENTS', callback_data='a:referrals:10')],
    ])


def recent_referrals_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(str(size), callback_data=f'a:referrals:{size}')
         for size in REFERRAL_SAMPLE_SIZES],
        [InlineKeyboardButton('⬅️ MENU ADMIN', callback_data='a:menu')],
    ])


def referral_actions(link: str | None, menu: InlineKeyboardMarkup | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton('🛠 Mon lien ne marche pas', callback_data='u:checkref')]]
    if link:
        share = 'https://t.me/share/url?' + urlencode({'url': link})
        rows.insert(0, [InlineKeyboardButton('↗️ Partager mon lien', url=share)])
    return InlineKeyboardMarkup(rows + (list(menu.inline_keyboard) if menu else []))


def group_list(rows) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(f"{'📢' if g.role.value == 'pub' else '🔐' if g.role.value == 'vip' else '⏳'} {g.title}", callback_data=f'a:g:{g.chat_id}')] for g in rows]
    buttons.append([InlineKeyboardButton('⬅️ MENU', callback_data='a:menu')])
    return InlineKeyboardMarkup(buttons)


def pending_group(chat_id: int, can_configure: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_configure:
        rows.append([InlineKeyboardButton('📢 GROUPE PUB', callback_data=f'a:role:{chat_id}:pub'), InlineKeyboardButton('🔐 GROUPE VIP', callback_data=f'a:role:{chat_id}:vip')])
    rows.append([InlineKeyboardButton('🔄 VÉRIFIER', callback_data=f'a:check:{chat_id}'), InlineKeyboardButton('🚫 REFUSER', callback_data=f'a:reject:{chat_id}')])
    return InlineKeyboardMarkup(rows)


def manage_pub(chat_id: int, authorized: bool = True) -> InlineKeyboardMarkup:
    state_button = (
        InlineKeyboardButton('⏸ DÉSACTIVER', callback_data=f'a:disablepub:{chat_id}')
        if authorized else
        InlineKeyboardButton('▶️ RÉACTIVER', callback_data=f'a:enablepub:{chat_id}')
    )
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📝 TEXTE PUB', callback_data=f'a:adtext:{chat_id}'), InlineKeyboardButton('🖼 IMAGE PUB', callback_data=f'a:adphoto:{chat_id}')],
        [InlineKeyboardButton('🔗 ASSOCIER VIP', callback_data=f'a:choosevip:{chat_id}'), InlineKeyboardButton('👁 PRÉVISUALISER', callback_data=f'a:preview:{chat_id}')],
        [InlineKeyboardButton('📢 PUBLIER', callback_data=f'a:publish:{chat_id}'), InlineKeyboardButton('📊 STATS GROUPE', callback_data=f'a:gstats:{chat_id}')],
        [state_button],
        [InlineKeyboardButton('🗑 SUPPRIMER & LIBÉRER', callback_data=f'a:deletepub:{chat_id}')],
        [InlineKeyboardButton('⬅️ GROUPES', callback_data='a:groups')],
    ])


def delete_pub_confirm(chat_id: int, campaign_count: int, pending_count: int, link_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f'🗑 CONFIRMER — LIBÉRER {campaign_count}',
            callback_data=f'a:deletepubconfirm:{chat_id}',
        )],
        [InlineKeyboardButton('❌ ANNULER', callback_data=f'a:g:{chat_id}')],
    ])


def choose_vip(pub_id: int, vips) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(v.title, callback_data=f'a:setvip:{pub_id}:{v.chat_id}')] for v in vips]
    rows.append([InlineKeyboardButton('⬅️ RETOUR', callback_data=f'a:g:{pub_id}')])
    return InlineKeyboardMarkup(rows)


def user_menu(can_use: bool = False, missing: int = 0, blocked_label: str | None = None, *, lifetime: bool = False, permanent: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton('📊 MON COMPTEUR', callback_data='u:counter'), InlineKeyboardButton('🔗 MON LIEN', callback_data='u:link')],
    ]
    if permanent:
        rows.append([InlineKeyboardButton('👑 ACCÉDER AU VIP À VIE', callback_data='u:lifetime')])
    elif can_use:
        rows.append([InlineKeyboardButton('🔐 UTILISER MES MINUTES', callback_data='u:use')])
    elif blocked_label:
        rows.append([InlineKeyboardButton(blocked_label, callback_data='u:counter')])
    elif missing > 0:
        rows.append([InlineKeyboardButton(f'🔒 ENCORE {missing} MINUTES', callback_data='u:counter')])
    else:
        # Sécurité d'affichage : ne jamais montrer « ENCORE 0 MINUTES ».
        rows.append([InlineKeyboardButton('🔄 ACTUALISER MON ACCÈS', callback_data='u:counter')])
    if lifetime and not permanent:
        rows.append([InlineKeyboardButton('👑 MES ACCÈS À VIE', callback_data='u:lifetime')])
    rows.append([InlineKeyboardButton('🏅 MES RANGS', callback_data='u:ranks')])
    rows.append([InlineKeyboardButton('🏆 DÉFI VIP À VIE · FACULTATIF', callback_data='u:challenge')])
    rows.append([InlineKeyboardButton('📖 RÈGLES', callback_data='u:rules')])
    return InlineKeyboardMarkup(rows)


def start_campaign() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🚀 CRÉER MON LIEN', callback_data='u:create')],
        [InlineKeyboardButton('📖 COMMENT ÇA MARCHE ?', callback_data='u:rules')],
    ])


def vip_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton('✅ GÉNÉRER MON LIEN VIP', callback_data='u:confirmvip')], [InlineKeyboardButton('❌ ANNULER', callback_data='u:counter')]])


def broadcast_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('✅ ENVOYER À TOUS', callback_data='a:broadcast:send')],
        [InlineKeyboardButton('❌ ANNULER', callback_data='a:broadcast:cancel')],
    ])

