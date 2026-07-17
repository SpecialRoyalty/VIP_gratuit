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
        [InlineKeyboardButton('🚫 REFUSER', callback_data=f'a:role:{chat_id}:blocked')],
    ])


def proof_review_keyboard(proof_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('✅ ACCEPTER', callback_data=f'a:proof:{proof_id}:approve'), InlineKeyboardButton('❌ REFUSER', callback_data=f'a:proof:{proof_id}:reject')],
        [InlineKeyboardButton('🚫 BANNIR', callback_data=f'a:proof:{proof_id}:ban')],
    ])
