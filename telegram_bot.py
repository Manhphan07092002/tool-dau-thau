import telebot
import sqlite3
import json
import time
import pandas as pd
import os

def load_telegram_config():
    try:
        conn = sqlite3.connect("bids.db")
        c = conn.cursor()
        c.execute("SELECT value FROM config WHERE key='app_config'")
        row = c.fetchone()
        conn.close()
        if row:
            config = json.loads(row[0])
            token = config.get("TELEGRAM_TOKEN", "").strip()
            if token.lower().startswith("bot"):
                token = token[3:]
            return token
    except Exception:
        pass
    return ""

def search_bids(keyword):
    try:
        conn = sqlite3.connect("bids.db")
        query = """
        SELECT ten, chu_dau_tu, gia_du_toan, ngay_dang, link, diem_phu_hop 
        FROM bids_full 
        WHERE LOWER(ten) LIKE ? OR LOWER(chu_dau_tu) LIKE ? OR LOWER(ma_tbmt) LIKE ? OR LOWER(dia_diem) LIKE ?
        ORDER BY ngay_dang DESC LIMIT 5
        """
        kw = f"%{keyword.lower()}%"
        df = pd.read_sql_query(query, conn, params=(kw, kw, kw, kw))
        conn.close()
        return df
    except Exception as e:
        print(e)
        return pd.DataFrame()

TOKEN = load_telegram_config()
if not TOKEN:
    print("❌ Không tìm thấy Telegram Token. Chatbot không thể khởi động.")
    exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🤖 <b>Chào mừng bạn đến với Trợ Lý Đấu Thầu AI!</b>\n\n"
        "Tôi là chatbot tự động giúp bạn theo dõi và tra cứu gói thầu 24/7.\n\n"
        "💡 <b>CÁCH TRA CỨU:</b>\n"
        "Bạn không cần gõ lệnh phức tạp, hãy nhắn cho tôi một <b>từ khóa bất kỳ</b> (Tên công ty, tên dự án, mã thông báo mời thầu, hoặc Tỉnh/Thành phố).\n"
        "<i>Ví dụ: Hãy thử nhắn 'Mobifone' hoặc 'Hà Nội'</i>\n\n"
        "Tôi sẽ lục tung kho dữ liệu khổng lồ và gửi cho bạn Top 5 gói thầu mới nhất khớp với từ khóa!"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def handle_search(message):
    keyword = message.text.strip()
    if len(keyword) < 2:
        bot.reply_to(message, "⚠️ Vui lòng nhập từ khóa dài hơn (ít nhất 2 ký tự) để tìm kiếm chính xác.")
        return
        
    bot.send_chat_action(message.chat.id, 'typing')
    
    df_results = search_bids(keyword)
    
    if df_results.empty:
        bot.reply_to(message, f"❌ Không tìm thấy gói thầu nào liên quan đến từ khóa <b>'{keyword}'</b> trong CSDL hiện tại.\n<i>(Hãy thử tìm với từ khóa khác ngắn gọn hơn)</i>")
    else:
        response = f"🔍 <b>Kết quả tìm kiếm cho: '{keyword}'</b>\n"
        response += f"<i>(Hiển thị {len(df_results)} gói thầu mới nhất)</i>\n\n"
        
        for idx, row in df_results.iterrows():
            stars = "⭐" * int(row['diem_phu_hop']) if pd.notna(row['diem_phu_hop']) and int(row['diem_phu_hop']) > 0 else ""
            response += f"📦 <b>{idx+1}. {row['ten']}</b>\n"
            response += f"🏢 <b>CĐT:</b> {row['chu_dau_tu']}\n"
            response += f"💰 <b>Giá:</b> {row['gia_du_toan']}\n"
            response += f"📅 <b>Ngày đăng:</b> {row['ngay_dang']} {f'| Tiềm năng: {stars}' if stars else ''}\n"
            response += f"🔗 <a href='{row['link']}'>Nhấn để xem Hồ sơ gốc</a>\n"
            response += "➖➖➖➖➖➖➖➖\n"
            
        bot.reply_to(message, response, disable_web_page_preview=True)

if __name__ == "__main__":
    print("🤖 Chatbot đang khởi động và lắng nghe tin nhắn...")
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            print(f"Lỗi kết nối bot: {e}. Đang thử lại sau 5s...")
            time.sleep(5)
