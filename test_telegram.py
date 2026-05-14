import sqlite3
import json
import requests
import sys

def test_telegram():
    print("========================================")
    print("🔍 KIỂM TRA KẾT NỐI TELEGRAM BOT 🔍")
    print("========================================")
    
    try:
        # 1. Đọc cấu hình từ Database
        print("1. Đang đọc cấu hình từ Database...")
        conn = sqlite3.connect("bids.db")
        c = conn.cursor()
        c.execute("SELECT value FROM config WHERE key='app_config'")
        row = c.fetchone()
        conn.close()
        
        if not row:
            print("❌ Lỗi: Không tìm thấy bất kỳ cấu hình nào trong Database.")
            print("👉 Vui lòng mở Giao diện Web, điền thông tin Token/Chat ID và bấm LƯU lại.")
            return
            
        config = json.loads(row[0])
        token = config.get("TELEGRAM_TOKEN", "").strip()
        if token.lower().startswith("bot"):
            token = token[3:]
        chat_id = str(config.get("TELEGRAM_CHAT_ID", "")).strip()
        
        if not token or not chat_id:
            print("❌ Lỗi: Token hoặc Chat ID đang bị bỏ trống!")
            print(f"   - Token hiện tại: '{token}'")
            print(f"   - Chat ID hiện tại: '{chat_id}'")
            return
            
        print(f"✅ Đã tìm thấy cấu hình:")
        print(f"   - Bot Token : {token[:8]}...{token[-4:] if len(token)>12 else ''}")
        print(f"   - Chat ID   : {chat_id}")
        print("")
        
        # 2. Gửi tin nhắn test
        print("2. Đang gửi tin nhắn test đến Telegram...")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "🤖 <b>Xác nhận kết nối thành công!</b>\n\nĐây là tin nhắn test từ Hệ thống Đấu Thầu AI.\nNếu bạn nhận được tin nhắn này, tính năng thông báo đang hoạt động hoàn hảo!",
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        # 3. Phân tích kết quả
        if response.status_code == 200:
            print("\n🎉 THÀNH CÔNG! Đã gửi tin nhắn đến điện thoại của bạn.")
            print("👉 Hãy mở ứng dụng Telegram lên để kiểm tra ngay nhé!")
        else:
            print(f"\n❌ THẤT BẠI! Lỗi từ máy chủ Telegram (Mã {response.status_code}):")
            
            error_data = response.json()
            error_msg = error_data.get('description', response.text)
            print(f"🔴 Chi tiết lỗi: {error_msg}")
            
            print("\n💡 GỢI Ý KHẮC PHỤC:")
            if "Not Found" in error_msg or "Unauthorized" in error_msg:
                print(" - Bot Token của bạn không chính xác. Hãy lấy lại mã token từ @BotFather.")
            elif "chat not found" in error_msg:
                print(" - Chat ID không tồn tại. Hãy dùng bot @userinfobot để lấy chính xác ID của bạn.")
            elif "bot was blocked by the user" in error_msg:
                print(" - Bạn đã block bot này. Hãy vào Telegram, tìm tên bot và bấm UNBLOCK / RESTART.")
            elif "bot can't initiate conversation" in error_msg:
                print(" - RẤT QUAN TRỌNG: Bot không thể tự động nhắn tin cho bạn trước!")
                print(" - 👉 Hãy vào Telegram, tìm kiếm bot của bạn và BẤM NÚT /start TRƯỚC KHI THỬ LẠI.")
            else:
                print(" - Hãy kiểm tra lại kết nối mạng hoặc thử lại sau.")
                
    except Exception as e:
        print(f"\n❌ Lỗi hệ thống nghiêm trọng: {str(e)}")

if __name__ == "__main__":
    test_telegram()
