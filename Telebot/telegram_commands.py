from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from decimal import Decimal

def show_games(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🎲 Roulette", callback_data='game_roulette'),
         InlineKeyboardButton("♠️ Blackjack", callback_data='game_blackjack')],
        [InlineKeyboardButton("🎰 Coin Flip", callback_data='game_coinflip')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Choose a game:", reply_markup=reply_markup)

def show_shop(update: Update, context: CallbackContext):
    from app import ITEMS  # Import here to avoid circular imports
    
    message = "🛍️ Available Items:\n\n"
    for item in ITEMS:
        message += f"• {item['name']} - ${item['price']}\n"
    
    message += "\nTo purchase an item, use:\n/buy item_name"
    update.message.reply_text(message)

def buy_item(update: Update, context: CallbackContext):
    from app import ITEMS, USERS
    
    if not context.args:
        update.message.reply_text("Please specify an item name")
        return
    
    item_name = " ".join(context.args)
    item = next((item for item in ITEMS if item['name'].lower() == item_name.lower()), None)
    
    if not item:
        update.message.reply_text("Item not found")
        return
    
    telegram_id = str(update.effective_user.id)
    user = next((u for u in USERS.values() if getattr(u, 'telegram_id', None) == telegram_id), None)
    
    if not user:
        update.message.reply_text("Please link your account first using /link command")
        return
    
    if user.balance >= item['price']:
        user.balance -= Decimal(str(item['price']))
        user.purchase_history.append(item)
        update.message.reply_text(f"Successfully purchased {item['name']} for ${item['price']}")
    else:
        update.message.reply_text("Insufficient balance")

def show_stats(update: Update, context: CallbackContext):
    from app import USERS
    
    telegram_id = str(update.effective_user.id)
    user = next((u for u in USERS.values() if getattr(u, 'telegram_id', None) == telegram_id), None)
    
    if not user:
        update.message.reply_text("Please link your account first using /link command")
        return
    
    stats = (f"📊 Your Statistics:\n\n"
            f"Balance: ${user.balance}\n"
            f"Level: {user.level}\n"
            f"Reward Points: {user.reward_points}\n\n"
            f"Recent Purchases:\n")
    
    for item in user.purchase_history[-5:]:  # Show last 5 purchases
        stats += f"• {item['name']} - ${item['price']}\n"
    
    update.message.reply_text(stats) 