from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🩺 SANTÉ', callback_data='a:health'), InlineKeyboardButton('📊 STATISTIQUES', callback_data='a:stats')],
        [InlineKeyboardButton('👥 GROUPES', callback_data='a:groups'), InlineKeyboardButton('🚫 MOTS INTERDITS', callback_data='a:words')],
        [InlineKeyboardButton('📣 BROADCAST PRIVÉ', callback_data='a:broadcast')],
    ])


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


def manage_pub(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📝 TEXTE PUB', callback_data=f'a:adtext:{chat_id}'), InlineKeyboardButton('🖼 IMAGE PUB', callback_data=f'a:adphoto:{chat_id}')],
        [InlineKeyboardButton('🔗 ASSOCIER VIP', callback_data=f'a:choosevip:{chat_id}'), InlineKeyboardButton('👁 PRÉVISUALISER', callback_data=f'a:preview:{chat_id}')],
        [InlineKeyboardButton('📢 PUBLIER', callback_data=f'a:publish:{chat_id}'), InlineKeyboardButton('📊 STATS GROUPE', callback_data=f'a:gstats:{chat_id}')],
        [InlineKeyboardButton('⬅️ GROUPES', callback_data='a:groups')],
    ])


def choose_vip(pub_id: int, vips) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(v.title, callback_data=f'a:setvip:{pub_id}:{v.chat_id}')] for v in vips]
    rows.append([InlineKeyboardButton('⬅️ RETOUR', callback_data=f'a:g:{pub_id}')])
    return InlineKeyboardMarkup(rows)


def user_menu(can_use: bool = False, missing: int = 0) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton('📊 MON COMPTEUR', callback_data='u:counter'), InlineKeyboardButton('🔗 MON LIEN', callback_data='u:link')],
    ]
    if can_use:
        rows.append([InlineKeyboardButton('🔐 UTILISER MES MINUTES', callback_data='u:use')])
    else:
        rows.append([InlineKeyboardButton(f'🔒 ENCORE {max(0, missing)} INVITATIONS', callback_data='u:counter')])
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
