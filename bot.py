import os
import telebot
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import threading

TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cricket_betting.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(50), unique=True, nullable=False)
    balance = db.Column(db.Float, default=100.0)

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(50), nullable=False)
    match_info = db.Column(db.String(100), nullable=False)
    team = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='PENDING')

with app.app_context():
    db.create_all()

# 1. /start Command Handler (Telegram ID based registration)
@bot.message_handler(commands=['start'])
def send_welcome(message):
    with app.app_context():
        tg_id = str(message.from_user.id)
        user = User.query.filter_by(telegram_id=tg_id).first()
        if not user:
            user = User(telegram_id=tg_id, balance=100.0)
            db.session.add(user)
            db.session.commit()
        
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        telebot.types.KeyboardButton('🏏 Live Cricket Matches'),
        telebot.types.KeyboardButton('💰 My Wallet'),
        telebot.types.KeyboardButton('📥 Deposit (UPI / QR)'),
        telebot.types.KeyboardButton('📤 Withdraw')
    )
    bot.reply_to(
        message, 
        "🏏 **Welcome to Cricket Betting Bot!**\n\n"
        "Live score check karein, wallet manage karein aur matches par bet lagayein.", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

# 2. Live Cricket Matches (Cricbuzz Redirect)
@bot.message_handler(func=lambda message: message.text == '🏏 Live Cricket Matches')
def live_matches(message):
    markup = telebot.types.InlineKeyboardMarkup()
    cricbuzz_button = telebot.types.InlineKeyboardButton(
        "🔗 Open Cricbuzz Live Scores", 
        url="https://www.cricbuzz.com/cricket-match/live-scores"
    )
    markup.add(cricbuzz_button)
    
    bot.reply_to(
        message, 
        "🔴 **Live Cricket Matches**\n\n"
        "Cricbuzz par score dekhne ke baad niche diye gaye format me bet lagayein:\n\n"
        "👉 **Bet Format:**\n`/bet <Match> <Team> <Amount>`\n"
        "*Example:* `/bet INDvsAUS India 200`", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

# 3. Wallet Balance Check
@bot.message_handler(func=lambda message: message.text == '💰 My Wallet')
def check_wallet(message):
    with app.app_context():
        tg_id = str(message.from_user.id)
        user = User.query.filter_by(telegram_id=tg_id).first()
        balance = user.balance if user else 0.0
    bot.reply_to(message, f"👤 **Your Account Summary**\n💳 Wallet Balance: ₹{balance:.2f}")

# 4. Deposit Section (Minimum ₹300)
@bot.message_handler(func=lambda message: message.text == '📥 Deposit (UPI / QR)')
def deposit_menu(message):
    upi_id = "BHARATPE2B0I0C8Z0Q12576@unitype"
    
    deposit_text = (
        "📲 **Deposit via UPI / QR Code**\n\n"
        "⚠️ **Minimum Deposit:** ₹300\n\n"
        "1. Niche di gayi UPI ID par payment karein:\n"
        f"🆔 UPI ID: `{upi_id}`\n\n"
        "2. Payment ke baad apna UTR number is format me bhejein:\n"
        "`/pay <UTR_Number> <Amount>`\n\n"
        "*(Example: `/pay 40392819283 300`)*"
    )
    bot.reply_to(message, deposit_text, parse_mode="Markdown")

# 5. Payment Verification Command (Checking Minimum ₹300)
@bot.message_handler(commands=['pay'])
def handle_payment_proof(message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Galat format! Use karein: `/pay <UTR_Number> <Amount>`", parse_mode="Markdown")
            return
            
        utr_no = parts[1]
        amount = float(parts[2])
        
        if amount < 300:
            bot.reply_to(message, "❌ **Minimum deposit amount ₹300 hai!** Kripya ₹300 ya usse zyada deposit karein.")
            return
        
        bot.reply_to(
            message, 
            f"⏳ **Payment Request Received!**\n\n"
            f"UTR: {utr_no}\n"
            f"Amount: ₹{amount}\n\n"
            "Aapka payment verify hone ke baad balance wallet me add kar diya jayega.", 
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, "⚠️ Error! Kripya sahi format use karein.")

# 6. Bet Placement Command
@bot.message_handler(commands=['bet'])
def place_bet(message):
    try:
        parts = message.text.split()
        if len(parts) < 4:
            bot.reply_to(message, "⚠️ **Galat Format!**\nUse karein: `/bet <Match> <Team> <Amount>`", parse_mode="Markdown")
            return
            
        match_name = parts[1]
        team_name = parts[2]
        amount = float(parts[3])
        tg_id = str(message.from_user.id)
        
        with app.app_context():
            user = User.query.filter_by(telegram_id=tg_id).first()
            if not user or user.balance < amount:
                bot.reply_to(message, "❌ Aapke wallet me itna balance nahi hai! Pehle deposit karein.")
                return
                
            user.balance -= amount
            new_bet = Bet(telegram_id=tg_id, match_info=match_name, team=team_name, amount=amount, status='PENDING')
            db.session.add(new_bet)
            db.session.commit()
            rem_balance = user.balance
        
        bot.reply_to(
            message, 
            f"✅ **Bet Successfully Placed!**\n\n"
            f"🏟 Match: {match_name}\n"
            f"🏆 Team: {team_name}\n"
            f"💰 Amount: ₹{amount}\n"
            f"💳 Remaining Balance: ₹{rem_balance:.2f}", 
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, "⚠️ Kuch error aayi hai. Kripya sahi format use karein.")

# 7. Withdraw Section (Min ₹100 & 1% Fee Deduction)
@bot.message_handler(func=lambda message: message.text == '📤 Withdraw')
def withdraw_menu(message):
    bot.reply_to(
        message, 
        "📤 **Withdrawal Request**\n\n"
        "⚠️ **Rules:**\n"
        "• Minimum Withdrawal: ₹100\n"
        "• Processing Fee: 1% deduction on withdrawal amount\n\n"
        "Apne account me paise lene ke liye yeh format use karein:\n"
        "`/withdraw <Amount> <UPI_ID>`\n"
        "*Example:* `/withdraw 500 yourname@okaxis`",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['withdraw'])
def process_withdraw(message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Sahi format use karein: `/withdraw <Amount> <UPI_ID>`", parse_mode="Markdown")
            return
            
        amount = float(parts[1])
        upi_payout = parts[2]
        tg_id = str(message.from_user.id)
        
        if amount < 100:
            bot.reply_to(message, "⚠️ Minimum withdrawal amount ₹100 hai.")
            return
            
        with app.app_context():
            user = User.query.filter_by(telegram_id=tg_id).first()
            if not user or user.balance < amount:
                bot.reply_to(message, "❌ Aapke wallet me itna balance nahi hai!")
                return
                
            fee = amount * 0.01
            final_payout = amount - fee
                
            user.balance -= amount
            db.session.commit()
            rem_balance = user.balance
        
        bot.reply_to(
            message, 
            f"✅ **Withdrawal Request Submitted!**\n\n"
            f"💰 Requested Amount: ₹{amount}\n"
            f"📉 Processing Fee (1%): ₹{fee:.2f}\n"
            f"💸 You Will Get: **₹{final_payout:.2f}**\n"
            f"📱 UPI ID: {upi_payout}\n"
            f"⏳ Status: Pending\n"
            f"💳 Remaining Balance: ₹{rem_balance:.2f}", 
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, "⚠️ Kuch error aayi hai. Dobara koshish karein.")

# Flask Server Route for 24/7 Uptime
@app.route('/')
def home():
    return "Cricket Betting Bot is live and running 24/7!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.start()
    
    print("Cricket Bot Polling Started...")
    bot.infinity_polling()
