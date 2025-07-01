from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal
import random
import requests
import os
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'supersecretkey')
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# NOWPayments API configuration
NOWPAYMENTS_API_KEY = os.environ.get('NOWPAYMENTS_API_KEY', 'your_nowpayments_api_key')
NOWPAYMENTS_API_URL = "https://api.nowpayments.io/v1"

# Sample data for the shop
ITEMS = [
    {'id': 1, 'name': 'Item 1', 'price': 10},
    {'id': 2, 'name': 'Item 2', 'price': 15},
    {'id': 3, 'name': 'Item 3', 'price': 20},
]

next_item_id = 4

# Sample user data
USERS = {}

class User(UserMixin):
import datetime

class User(UserMixin):
    def __init__(self, id, username, password, balance=Decimal('100.00'), role='user'):
        self.id = id
        self.username = username
        self.password = password
        self.balance = balance
        self.orders = [] # Stores list of order dictionaries, e.g. {'order_id': 'ORD-XYZ', 'items': [{'id':1, 'name':'Item1', 'price':10, 'quantity':1}], 'total_amount': 10, 'timestamp': 'YYYY-MM-DD HH:MM:SS'}
        self.level = 1
        self.reward_points = 0
        self.telegram_id = None
        self.cart = {} # item_id: quantity
        self.role = role # 'user' or 'admin'

    def get_id(self):
        return self.id

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def is_admin(self):
        return self.role == 'admin'

@login_manager.user_loader
def load_user(user_id):
    return USERS.get(user_id)

# Helper to generate a unique order ID
def generate_order_id():
    return f"ORD-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = next((user for user in USERS.values() if user.username == username), None)
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.')
            return redirect(url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        user_id = str(len(USERS) + 1)
        # First user registered is admin, others are 'user'
        role = 'admin' if not USERS else 'user'
        user = User(user_id, username, hashed_password, role=role)
        USERS[user_id] = user
        flash(f'Registered successfully as {role}. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

def update_user_rewards(user):
    total_spent = sum(order['total_amount'] for order in user.orders)
    user.reward_points = int(total_spent) # Example: 1 point per dollar spent
    user.level = user.reward_points // 50 + 1

@app.route('/')
@login_required
def index():
    cart_items_details = []
    total_cart_price = Decimal('0.00')
    if current_user.cart:
        for item_id, quantity in current_user.cart.items():
            item = next((i for i in ITEMS if i['id'] == item_id), None)
            if item:
                cart_items_details.append({'item': item, 'quantity': quantity, 'total_price': item['price'] * quantity})
                total_cart_price += item['price'] * quantity
    return render_template('index.html', items=ITEMS, user=current_user, cart_items_details=cart_items_details, total_cart_price=total_cart_price)

@app.route('/add_to_cart/<int:item_id>')
@login_required
def add_to_cart(item_id):
    item = next((i for i in ITEMS if i['id'] == item_id), None)
    if item:
        current_user.cart[item_id] = current_user.cart.get(item_id, 0) + 1
        flash(f'Added {item["name"]} to cart.')
    else:
        flash('Item not found.')
    return redirect(url_for('index'))

@app.route('/remove_from_cart/<int:item_id>')
@login_required
def remove_from_cart(item_id):
    item = next((i for i in ITEMS if i['id'] == item_id), None)
    if item and item_id in current_user.cart:
        if current_user.cart[item_id] > 1:
            current_user.cart[item_id] -= 1
        else:
            del current_user.cart[item_id]
        flash(f'Removed {item["name"]} from cart.')
    else:
        flash('Item not found in cart.')
    return redirect(url_for('index'))

@app.route('/clear_cart')
@login_required
def clear_cart():
    current_user.cart = {}
    flash('Cart cleared.')
    return redirect(url_for('index'))

@app.route('/checkout')
@login_required
def checkout():
    total_cart_price = Decimal('0.00')
    if not current_user.cart:
        flash('Your cart is empty.')
        return redirect(url_for('index'))

    for item_id, quantity in current_user.cart.items():
        item = next((i for i in ITEMS if i['id'] == item_id), None)
        if item:
            total_cart_price += item['price'] * quantity
        else:
            flash(f'Item with ID {item_id} not found. Please review your cart.')
            # Potentially remove missing items from cart here
            return redirect(url_for('index')) # Or redirect to a cart view page

    if current_user.balance >= total_cart_price:
        ordered_items_details = []
        for item_id, quantity in current_user.cart.items():
            item = next((i for i in ITEMS if i['id'] == item_id), None)
            if item: # Should always be true if cart is consistent
                ordered_items_details.append({
                    'id': item['id'],
                    'name': item['name'],
                    'price': item['price'],
                    'quantity': quantity
                })
            # In a real app, you'd also reduce stock here

        new_order = {
            'order_id': generate_order_id(),
            'items': ordered_items_details,
            'total_amount': total_cart_price,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        current_user.orders.append(new_order)
        current_user.balance -= total_cart_price
        update_user_rewards(current_user) # Recalculate rewards based on new order history
        current_user.cart = {} # Clear cart after purchase
        flash(f'Checkout successful! Total: ${total_cart_price}. Order ID: {new_order["order_id"]}')
    else:
        flash('Insufficient balance for checkout.')
    return redirect(url_for('index'))

@app.route('/order_history')
@login_required
def order_history():
    return render_template('order_history.html', orders=current_user.orders)

@app.route('/add_item', methods=['POST'])
@login_required
def add_item():
    global next_item_id
    name = request.form['name']
    price = Decimal(request.form['price'])
    ITEMS.append({'id': next_item_id, 'name': name, 'price': price})
    next_item_id += 1
    return redirect(url_for('index'))

@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    item = next((item for item in ITEMS if item['id'] == item_id), None)
    if request.method == 'POST':
        item['name'] = request.form['name']
        item['price'] = Decimal(request.form['price'])
        return redirect(url_for('index'))
    return render_template('edit_item.html', item=item)

@app.route('/delete_item/<int:item_id>')
@login_required
def delete_item(item_id):
    global ITEMS
    ITEMS = [item for item in ITEMS if item['id'] != item_id]
    return redirect(url_for('index'))

@app.route('/purchase_item/<int:item_id>')
@login_required
def purchase_item(item_id):
    item = next((item for item in ITEMS if item['id'] == item_id), None)
    user = current_user
    if item and user.balance >= item['price']:
        user.balance -= item['price']
        user.purchase_history.append(item)
        update_user_rewards(user)
        flash(f'Purchased {item["name"]} for ${item["price"]}')
    else:
        flash('Insufficient balance or item not found')
    return redirect(url_for('index'))

@app.route('/flip_coin')
@login_required
def flip_coin():
    user = current_user
    if user.balance < 1:
        flash('Insufficient balance to play the game')
    else:
        user.balance -= Decimal('1')
        result = random.choice(['Heads', 'Tails'])
        if result == 'Heads':
            user.balance += Decimal('2')
            flash('You won! Your balance has been updated.')
        else:
            flash('You lost! Better luck next time.')
    return redirect(url_for('index'))

@app.route('/add_balance', methods=['POST'])
@login_required
def add_balance():
    amount = Decimal(request.form['amount'])
    current_user.balance += amount
    flash(f'Added ${amount} to your balance')
    return redirect(url_for('index'))

@app.route('/crypto_payment', methods=['POST'])
@login_required
def crypto_payment():
    amount = request.form['amount']
    currency = request.form['currency']
    payment_data = {
        "price_amount": amount,
        "price_currency": "usd",
        "pay_currency": currency,
        "ipn_callback_url": "https://your-site.com/ipn",
        "order_id": "order0001",
        "order_description": f"Add balance ${amount} to {current_user.username}"
    }
    headers = {
        'x-api-key': NOWPAYMENTS_API_KEY,
        'Content-Type': 'application/json'
    }
    response = requests.post(f"{NOWPAYMENTS_API_URL}/payment", json=payment_data, headers=headers)
    if response.status_code == 201:
        payment = response.json()
        return redirect(payment['invoice_url'])
    else:
        flash('Error processing payment')
        return redirect(url_for('index'))

@app.route('/ipn', methods=['POST'])
def ipn():
    # Handle IPN from NOWPayments here
    data = request.json
    if data['payment_status'] == 'finished':
        # Find the user and update their balance
        user_id = data['order_id'].split('-')[1]
        amount = Decimal(data['price_amount'])
        user = USERS.get(user_id)
        if user:
            user.balance += amount
            flash(f'Added ${amount} to your balance via NOWPayments')
    return jsonify({"status": "success"})

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin():
        flash('Access denied: Admin privileges required.')
        return redirect(url_for('index'))
    return render_template('admin.html', users=USERS.values(), items=ITEMS)

# Decorator for admin required routes
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Apply admin_required to admin-specific item management routes
@app.route('/add_item', methods=['POST'])
@login_required
@admin_required
def add_item():
    global next_item_id
    name = request.form['name']
    price = Decimal(request.form['price'])
    ITEMS.append({'id': next_item_id, 'name': name, 'price': price})
    next_item_id += 1
    flash(f"Item '{name}' added successfully.", "success")
    return redirect(url_for('admin')) # Redirect to admin page

@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_item(item_id):
    item = next((item for item in ITEMS if item['id'] == item_id), None)
    if not item:
        flash("Item not found.", "danger")
        return redirect(url_for('admin'))
    if request.method == 'POST':
        item['name'] = request.form['name']
        item['price'] = Decimal(request.form['price'])
        flash(f"Item '{item['name']}' updated successfully.", "success")
        return redirect(url_for('admin'))
    return render_template('edit_item.html', item=item)

@app.route('/delete_item/<int:item_id>')
@login_required
@admin_required
def delete_item(item_id):
    global ITEMS
    item_to_delete = next((item for item in ITEMS if item['id'] == item_id), None)
    if item_to_delete:
        ITEMS = [item for item in ITEMS if item['id'] != item_id]
        flash(f"Item '{item_to_delete['name']}' deleted successfully.", "success")
    else:
        flash("Item not found.", "danger")
    return redirect(url_for('admin'))


# Additional Casino Games Routes

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = set(range(37)) - RED_NUMBERS - {0}

@app.route('/roulette')
@login_required
def roulette():
    return render_template('roulette.html', 
                         user=current_user,
                         red_numbers=RED_NUMBERS,
                         result=session.get('last_roulette_result'))

@app.route('/roulette/bet', methods=['POST'])
@login_required
def place_roulette_bet():
    bet_amount = Decimal(request.form['bet_amount'])
    bet_type = request.form['bet_type']
    number = int(request.form.get('number', 0))
    
    if bet_amount <= 0 or bet_amount > current_user.balance:
        flash('Invalid bet amount')
        return redirect(url_for('roulette'))
    
    # Deduct bet amount
    current_user.balance -= bet_amount
    
    # Spin the wheel
    result = random.randint(0, 36)
    won = False
    payout_multiplier = 0
    
    # Check win conditions
    if bet_type == 'straight' and result == number:
        won = True
        payout_multiplier = 35
    elif bet_type == 'red' and result in RED_NUMBERS:
        won = True
        payout_multiplier = 1
    elif bet_type == 'black' and result in BLACK_NUMBERS:
        won = True
        payout_multiplier = 1
    elif bet_type == 'even' and result != 0 and result % 2 == 0:
        won = True
        payout_multiplier = 1
    elif bet_type == 'odd' and result % 2 == 1:
        won = True
        payout_multiplier = 1
    elif bet_type == '1-18' and 1 <= result <= 18:
        won = True
        payout_multiplier = 1
    elif bet_type == '19-36' and 19 <= result <= 36:
        won = True
        payout_multiplier = 1
    
    # Calculate winnings
    if won:
        winnings = bet_amount * (payout_multiplier + 1)
        current_user.balance += winnings
        message = f'You won ${winnings}!'
    else:
        message = 'Better luck next time!'
    
    # Store result in session
    session['last_roulette_result'] = {
        'number': result,
        'message': message
    }
    
    return redirect(url_for('roulette'))

@app.route('/blackjack')
@login_required
def blackjack():
    # Implement blackjack game logic
    return render_template('blackjack.html', user=current_user)

# Add Telegram configuration
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'your_telegram_token')
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Telegram command handlers
def start(update: Update, context: CallbackContext):
    keyboard = [
        [KeyboardButton("💰 Balance"), KeyboardButton("🎲 Games")],
        [KeyboardButton("🛍️ Shop"), KeyboardButton("📊 Stats")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text(
        "Welcome to the Casino & Shop Bot!\n"
        "Use the keyboard below to navigate:",
        reply_markup=reply_markup
    )

def check_balance(update: Update, context: CallbackContext):
    telegram_id = str(update.effective_user.id)
    user = next((u for u in USERS.values() if getattr(u, 'telegram_id', None) == telegram_id), None)
    
    if user:
        update.message.reply_text(f"Your balance: ${user.balance}\n"
                                f"Level: {user.level}\n"
                                f"Reward points: {user.reward_points}")
    else:
        update.message.reply_text("Please link your account first using /link command")

def link_account(update: Update, context: CallbackContext):
    if len(context.args) != 2:
        update.message.reply_text("Usage: /link username password")
        return
    
    username, password = context.args
    user = next((u for u in USERS.values() if u.username == username), None)
    
    if user and user.check_password(password):
        user.telegram_id = str(update.effective_user.id)
        update.message.reply_text("Account linked successfully!")
    else:
        update.message.reply_text("Invalid username or password")

# Add these handlers to the dispatcher
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("balance", check_balance))
dispatcher.add_handler(CommandHandler("link", link_account))

if __name__ == '__main__':
    app.run(debug=True)
