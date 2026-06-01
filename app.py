import telebot
from telebot import apihelper
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request
import random
import string
import os
import json
import sys
import time

# --- 0. PENGATURAN JARINGAN (SUPER STABIL) ---
apihelper.CONNECT_TIMEOUT = 90
apihelper.READ_TIMEOUT = 90

# --- 1. SETUP FIREBASE ---
firebase_secrets = os.environ.get('FIREBASE_CREDENTIALS')
if firebase_secrets:
    cred_dict = json.loads(firebase_secrets)
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    raise ValueError("Firebase credentials tidak ditemukan di secrets!")

# --- 2. SETUP VARIABEL TELEGRAM ---
TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', '-1003908403936')) 
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
BOT_USERNAME = None

def get_bot_username():
    global BOT_USERNAME
    if not BOT_USERNAME:
        try:
            BOT_USERNAME = bot.get_me().username
        except Exception:
            BOT_USERNAME = "UsernameBotAnda"
    return BOT_USERNAME

def generate_hash(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# --- 3. LOGIKA BOT TELEGRAM ---

@bot.message_handler(content_types=['video', 'document', 'photo', 'animation'])
def handle_upload(message):
    print(f"📦 [SISTEM] Memproses file dari user: {message.from_user.id}", flush=True)
    
    # SISTEM ANTI-GAGAL JARINGAN
    forwarded_msg = None
    for attempt in range(3):
        try:
            forwarded_msg = bot.copy_message(CHANNEL_ID, message.chat.id, message.message_id)
            break
        except Exception as e:
            print(f"⚠️ Gagal (Percobaan {attempt+1}/3). ALASAN: {e}", flush=True)
            time.sleep(2)
            
    if not forwarded_msg:
        bot.reply_to(message, "❌ Gagal memproses file ke Channel. Silakan coba kirim ulang.")
        return

    try:
        msg_id = forwarded_msg.message_id
        hash_id = generate_hash()
        db.collection('videos').document(hash_id).set({
            'message_id': msg_id,
            'uploader_id': message.from_user.id
        })
        
        deep_link = f"https://t.me/{get_bot_username()}?start={hash_id}"
        
        pesan_balasan = (
            f"✅ File berhasil diamankan!\n\n"
            f"🔖 ID File: {hash_id}\n\n"
            f"🔗 Link Telegram Anda:\n{deep_link}\n\n"
            f"📝 Copy kode HTML di bawah ini dan paste di postingan Blogger Anda (Mode HTML):"
        )
        
        # Membuat format HTML siap copy-paste dengan warna oren
        html_code = (
            f'<div style="text-align: center; margin-top: 20px; margin-bottom: 20px;">\n'
            f'  <a href="{deep_link}" target="_blank" style="background-color: #ff5722; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; font-family: Arial, sans-serif; font-size: 16px;">\n'
            f'    ▶ BUKA VIDEO SEKARANG\n'
            f'  </a>\n'
            f'</div>'
        )

        bot.reply_to(message, pesan_balasan)
        # Mengirim kode HTML dalam format blok (agar bisa di-tap copy di HP/PC)
        bot.send_message(message.chat.id, f"```html\n{html_code}\n```", parse_mode='Markdown')
        
        print(f"🚀 [SUKSES] Deep link manual berhasil dibuat.", flush=True)
        
    except Exception as e:
        print(f"❌ [ERROR FATAL]: {e}", flush=True)
        bot.reply_to(message, "❌ Terjadi kesalahan sistem saat memproses link Anda.")

@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        text_parts = message.text.split()
        if len(text_parts) > 1:
            hash_id = text_parts[1]
            doc_ref = db.collection('videos').document(hash_id)
            doc = doc_ref.get()
            
            if doc.exists:
                msg_id = doc.to_dict().get('message_id')
                bot.copy_message(message.chat.id, CHANNEL_ID, msg_id)
            else:
                bot.reply_to(message, "❌ Link tidak valid atau file tidak ditemukan.")
        else:
            bot.reply_to(message, "👋 Halo! Kirimkan file kepada saya untuk dibuatkan link monetisasinya.")
    except Exception as e:
        pass

@bot.message_handler(func=lambda message: True, content_types=['text', 'sticker', 'voice', 'audio', 'location', 'contact'])
def handle_unknown(message):
    if message.text and message.text.startswith('/start'):
        return
    bot.reply_to(message, "🙏 Maaf, saya hanya bisa memproses file. Silakan kirimkan video/foto Anda!")

# --- 4. LOGIKA WEBHOOK (FLASK SERVER) ---
@app.route('/', methods=['GET'])
def index():
    return "Bot berjalan dengan aman 24/7!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    except Exception as e:
        return 'Error', 500
