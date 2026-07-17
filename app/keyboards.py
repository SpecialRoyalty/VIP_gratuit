from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def user_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📊 MON COMPTEUR', callback_data='u:counter'), InlineKeyboardButton('📝 TEXTE À PUBLIER', callback_data='u:text')],
        [InlineKeyboardButton('📸 MA PREUVE', callback_data='u:proof'), InlineKeyboardButton('🔐 MON ACCÈS VIP', callback_data='u:vip')],
        [InlineKeyboardButton('❓ AIDE', callback_data='u:help')],
    ])


def start_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🚀 COMMENCER', callback_data='u:begin')],
        [InlineKeyboardButton('📖 COMMENT ÇA MARCHE ?', callback_data='u:how')],
        [InlineKeyboardButton('❌ ANNULER', callback_data='u:cancel')],
    ])


def proof_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📸 ENVOYER MA CAPTURE', callback_data='u:proof')],
        [InlineKeyboardButton('❓ BESOIN D’AIDE', callback_data='u:help_publish')],
    ])


def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🩺 ÉTAT DU BOT', callback_data='a:health')],
        [InlineKeyboardButton('👥 GROUPES', callback_data='a:groups'), InlineKeyboardButton('📸 PREUVES', callback_data='a:proofs')],
        [InlineKeyboardButton('📊 STATISTIQUES', callback_data='a:stats'), InlineKeyboardButton('📢 PUBLIER LES PUBS', callback_data='a:post_ads')],
    ])


def group_role_keyboard(chat_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📢 GROUPE PUB', callback_data=f'a:role:{chat_id}:pub')],
        [InlineKeyboardButton('🔐 GROUPE VIP', callback_data=f'a:role:{chat_id}:vip')],
        [InlineKeyboardButton('🔄 VÉRIFIER LES DROITS', callback_data=f'a:recheck:{chat_id}')],
        [InlineKeyboardButton('🚫 REFUSER', callback_data=f'a:role:{chat_id}:blocked')],
    ])


def promote_required_keyboard(chat_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🔄 VÉRIFIER À NOUVEAU', callback_data=f'a:recheck:{chat_id}')],
        [InlineKeyboardButton('🚫 REFUSER LE GROUPE', callback_data=f'a:role:{chat_id}:blocked')],
    ])


def proof_review_keyboard(proof_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('✅ ACCEPTER', callback_data=f'a:proof:{proof_id}:approve'), InlineKeyboardButton('❌ REFUSER', callback_data=f'a:proof:{proof_id}:reject')],
        [InlineKeyboardButton('🚫 BANNIR', callback_data=f'a:proof:{proof_id}:ban')],
    ])


def group_manage_keyboard(chat_id: int, role: str):
    rows = []
    if role == 'pub':
        rows += [
            [InlineKeyboardButton('📝 TEXTE DE PUB', callback_data=f'a:cfg:{chat_id}:ad_text')],
            [InlineKeyboardButton('🖼 IMAGE DE PUB', callback_data=f'a:cfg:{chat_id}:ad_photo')],
            [InlineKeyboardButton('💬 TEXTE PRIVÉ /START', callback_data=f'a:cfg:{chat_id}:private_text')],
            [InlineKeyboardButton('🌄 IMAGE PRIVÉE /START', callback_data=f'a:cfg:{chat_id}:private_photo')],
            [InlineKeyboardButton('🔗 ASSOCIER AU VIP', callback_data=f'a:cfg:{chat_id}:vip')],
            [InlineKeyboardButton('👁 PRÉVISUALISER', callback_data=f'a:cfg:{chat_id}:preview')],
            [InlineKeyboardButton('📢 PUBLIER CETTE PUB', callback_data=f'a:cfg:{chat_id}:publish')],
        ]
    rows.append([InlineKeyboardButton('🔙 GROUPES', callback_data='a:groups')])
    return InlineKeyboardMarkup(rows)


def groups_list_keyboard(groups):
    rows = [[InlineKeyboardButton(f"{'📢' if g.role.value == 'pub' else '🔐' if g.role.value == 'vip' else '❔'} {g.title[:32]}", callback_data=f'a:group:{g.chat_id}')] for g in groups]
    rows.append([InlineKeyboardButton('🔙 MENU ADMIN', callback_data='a:menu')])
    return InlineKeyboardMarkup(rows)


def vip_choice_keyboard(pub_id: int, vip_groups):
    rows = [[InlineKeyboardButton(f'🔐 {g.title[:35]}', callback_data=f'a:setvip:{pub_id}:{g.chat_id}')] for g in vip_groups]
    rows.append([InlineKeyboardButton('🔙 RETOUR', callback_data=f'a:group:{pub_id}')])
    return InlineKeyboardMarkup(rows)
