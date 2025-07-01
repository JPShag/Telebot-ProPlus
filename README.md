# Telebot-ProPlus - Feel the power

# The Ultimate Telegram-Integrated Crypto-Powered E-Commerce and Gaming Extravaganza

A Flask application for managing an online shop with user authentication, crypto payments, and thrilling casino games, all seamlessly integrated with Telegram for an unparalleled shopping and gaming experience.

## Features

- User registration and login
- Add, edit, delete items
- Purchase items with balance
- Add balance using NOWPayments
- Coin flip game
- Casino games (Roulette and Blackjack)
- Admin dashboard
- Seamless integration with Telegram for shop management

## Setup

1. Clone the repository:
    ```bash
    git clone https://github.com/JPShag/Telebot-ProPlus.git
    cd MegaCryptoCasinoShop
    ```

2. Create a virtual environment and install dependencies:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3. Set up environment variables:
    ```bash
    export FLASK_SECRET_KEY='your_secret_key'
    export NOWPAYMENTS_API_KEY='your_nowpayments_api_key'
    ```

4. Run the application:
    ```bash
    python app.py
    ```

5. Access the application at `http://localhost:5000`.

## Deployment

To deploy this application on a server using Gunicorn and Nginx, follow the instructions provided in the setup guide.

## License

This project is licensed under the MIT License.
