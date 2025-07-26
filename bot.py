import os
import telebot
import yt_dlp
import sqlite3

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# ✅ إنشاء قاعدة البيانات لو مش موجودة
conn = sqlite3.connect("cache.db")
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS cache (
    url TEXT PRIMARY KEY,
    type TEXT,
    file_id TEXT,
    title TEXT
)""")
conn.commit()
conn.close()

def check_cache(url):
    conn = sqlite3.connect("cache.db")
    c = conn.cursor()
    c.execute("SELECT file_id, type, title FROM cache WHERE url=?", (url,))
    data = c.fetchone()
    conn.close()
    return data

def save_cache(url, file_type, file_id, title):
    conn = sqlite3.connect("cache.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO cache (url, type, file_id, title) VALUES (?, ?, ?, ?)",
              (url, file_type, file_id, title))
    conn.commit()
    conn.close()

user_choices = {}

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 ابعت لينك فيديو أو Playlist من يوتيوب")

@bot.message_handler(func=lambda m: m.text.startswith("http"))
def ask_type(message):
    user_choices[message.chat.id] = {"url": message.text}
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add("🎵 صوت", "🎥 فيديو")
    bot.send_message(message.chat.id, "تحب تنزلها صوت ولا فيديو؟", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["🎵 صوت", "🎥 فيديو"])
def ask_quality(message):
    user_choices[message.chat.id]["type"] = "audio" if message.text == "🎵 صوت" else "video"
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add("🎶 أعلى جودة", "144p", "360p", "720p")
    bot.send_message(message.chat.id, "اختار الجودة:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["🎶 أعلى جودة", "144p", "360p", "720p"])
def download(message):
    choice = user_choices.get(message.chat.id)
    if not choice:
        bot.send_message(message.chat.id, "❌ ابعت اللينك الأول.")
        return

    url = choice["url"]
    file_type = choice["type"]
    quality = message.text

    # ✅ فحص الكاش قبل التحميل
    cached = check_cache(url)
    if cached:
        file_id, cached_type, title = cached
        bot.send_message(message.chat.id, f"⚡ إرسال من الكاش: {title}")
        if cached_type == "audio":
            bot.send_audio(message.chat.id, file_id, title=title)
        else:
            bot.send_video(message.chat.id, file_id, caption=title)
        return

    bot.send_message(message.chat.id, "⏳ جاري التحميل...")

    # ✅ إعدادات yt-dlp حسب النوع والجودة
    if file_type == "audio":
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '%(title)s.%(ext)s',
            'noplaylist': False,
        }
    else:
        if quality == "🎶 أعلى جودة":
            fmt = 'bestvideo+bestaudio/best'
        else:
            fmt = f"bestvideo[height<={quality.replace('p','')}]+bestaudio/best"
        ydl_opts = {
            'format': fmt,
            'outtmpl': '%(title)s.%(ext)s',
            'noplaylist': False,
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            videos = info['entries'] if 'entries' in info else [info]

            for video in videos:
                title = video.get('title', 'Video')
                filename = ydl.prepare_filename(video)

                with open(filename, 'rb') as f:
                    if file_type == "audio":
                        msg = bot.send_audio(message.chat.id, f, title=title)
                        file_id = msg.audio.file_id
                    else:
                        msg = bot.send_video(message.chat.id, f, caption=title)
                        file_id = msg.video.file_id

                save_cache(url, file_type, file_id, title)
                os.remove(filename)

        bot.send_message(message.chat.id, "✅ تم الإرسال بنجاح!")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ حصل خطأ: {e}")

bot.polling()

