from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal
import random
import requests
import os

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
    def __init__(self, id, username, password, balance=Decimal('100.00')):
        self.id = id
        self.username = username
        self.password = password
        self.balance = balance
        self.purchase_history = []
        self.level = 1
        self.reward_points = 0

    def get_id(self):
        return self.id

    def check_password(self, password):
        return check_password_hash(self.password, password)

@login_manager.user_loader
def load_user(user_id):
    return USERS.get(user_id)

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
        user = User(user_id, username, hashed_password)
        USERS[user_id] = user
        flash('Registered successfully. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

def update_user_rewards(user):
    user.reward_points = sum(item['price'] for item in user.purchase_history)
    user.level = user.reward_points // 50 + 1

@app.route('/')
@login_required
def index():
    return render_template('index.html', items=ITEMS, user=current_user)

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
    if current_user.username != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    return render_template('admin.html', users=USERS.values(), items=ITEMS)

# Additional Casino Games Routes

@app.route('/roulette')
@login_required
def roulette():
    # Implement roulette game logic
    return render_template('roulette.html', user=current_user)

@app.route('/blackjack')
@login_required
def blackjack():
    # Implement blackjack game logic
    return render_template('blackjack.html', user=current_user)

if __name__ == '__main__':
    app.run(debug=True)
