import time
import json
import sqlite3
import sys
import subprocess
from datetime import datetime
import scraper_core

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

class ConsoleApp:
    def __init__(self):
        pass
        
    def log(self, message):
        # Print to console with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        # Flush stdout to see logs immediately in systemctl/docker
        sys.stdout.flush()
        
    def set_progress(self, current, total):
        # We can ignore progress bar in headless mode
        pass

def get_db_connection():
    conn = sqlite3.connect("bids.db")
    return conn

def run_now():
    app = ConsoleApp()
    app.log("Bắt đầu tiến trình quét dữ liệu...")
    try:
        scraper_core.run_scraper(app)
        app.log("HOÀN THÀNH TIẾN TRÌNH QUÉT!")
        scraper_core.export_to_excel(app, auto_send=True)
    except Exception as e:
        app.log(f"LỖI NGHIÊM TRỌNG: {str(e)}")

def start_scheduler():
    app = ConsoleApp()
    app.log("🚀 KHỞI ĐỘNG CHẾ ĐỘ TREO BOT TRÊN SERVER UBUNTU")
    
    # Start Streamlit Web Dashboard in the background
    app.log("🌐 Đang khởi động Web Dashboard (Streamlit)...")
    try:
        subprocess.Popen(["python3", "-m", "streamlit", "run", "dashboard.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.headless", "true"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        app.log("✅ Web Dashboard đã chạy ở cổng 8501. Truy cập qua http://<IP_Server>:8501")
    except Exception as e:
        app.log(f"⚠️ Không thể tự động khởi động Web Dashboard: {e}")
        
    # Start Telegram Chatbot in the background
    app.log("🤖 Đang khởi động Telegram Chatbot...")
    try:
        subprocess.Popen(["python3", "telegram_bot.py"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        app.log("✅ Chatbot đã sẵn sàng nhận lệnh từ Telegram!")
    except Exception as e:
        app.log(f"⚠️ Không thể tự động khởi động Chatbot: {e}")
        
    last_run_date = None
    
    while True:
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT value FROM config WHERE key='app_config'")
            row = c.fetchone()
            conn.close()
            
            if row:
                conf = json.loads(row[0])
                if conf.get("ENABLE_AUTO", False):
                    target_time = conf.get("AUTO_TIME", "08:00")
                    now_time = datetime.now().strftime("%H:%M")
                    today_date = datetime.now().strftime("%Y-%m-%d")
                    
                    if now_time == target_time and last_run_date != today_date:
                        app.log(f"⏰ Đã đến giờ hẹn ({target_time})! Bắt đầu quét...")
                        last_run_date = today_date
                        run_now()
                        app.log("Đang tiếp tục chờ đến ngày mai...")
        except Exception as e:
            app.log(f"Lỗi scheduler: {str(e)}")
            
        # Check every 30 seconds
        time.sleep(30)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        # Chạy ngay lập tức 1 lần
        run_now()
    else:
        # Chạy chế độ treo scheduler
        start_scheduler()
