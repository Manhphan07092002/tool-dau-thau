import sqlite3
import json
import os
import sys
import time
from datetime import datetime, timedelta
import pandas as pd
import requests
import google.generativeai as genai

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# SETUP SQLite DB
# ==========================================
def init_db():
    conn = sqlite3.connect("bids.db")
    c = conn.cursor()
    # Old table for backwards compatibility
    c.execute('''CREATE TABLE IF NOT EXISTS bids
                 (ma_tbmt TEXT PRIMARY KEY, ngay_quet TEXT)''')
                 
    # New full data table
    c.execute('''CREATE TABLE IF NOT EXISTS bids_full
                 (ma_tbmt TEXT PRIMARY KEY, ten TEXT, chu_dau_tu TEXT, 
                  linh_vuc TEXT, gia_du_toan TEXT, hinh_thuc TEXT, 
                  ngay_dang TEXT, dong_thau TEXT, dia_diem TEXT, 
                  link TEXT, diem_phu_hop INTEGER, ngay_quet TEXT, ai_summary TEXT)''')
                  
    # Config table
    c.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
    
    conn.commit()
    
    # Update schema if ai_summary doesn't exist
    try:
        c.execute("ALTER TABLE bids_full ADD COLUMN ai_summary TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Column already exists
        
    return conn

def is_scraped(conn, ma_tbmt):
    c = conn.cursor()
    c.execute("SELECT 1 FROM bids WHERE ma_tbmt=?", (ma_tbmt,))
    if c.fetchone(): return True
    c.execute("SELECT 1 FROM bids_full WHERE ma_tbmt=?", (ma_tbmt,))
    return c.fetchone() is not None

def save_scraped_full(conn, d):
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO bids_full 
                 (ma_tbmt, ten, chu_dau_tu, linh_vuc, gia_du_toan, hinh_thuc, 
                  ngay_dang, dong_thau, dia_diem, link, diem_phu_hop, ngay_quet, ai_summary) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
              (d["Mã TBMT"], d["Tên gói thầu"], d["Chủ đầu tư"], d["Lĩnh vực"], 
               d["Giá dự toán"], d["Hình thức LCNT"], d["Ngày đăng"], d["Đóng thầu"], 
               d["Địa điểm"], d["Link chi tiết"], d.get("Điểm", 0), 
               datetime.now().strftime("%Y-%m-%d %H:%M:%S"), d.get("AI Summary", "")))
    conn.commit()

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def get_v(label, text):
    if label not in text: return "N/A"
    return text.split(label)[1].split("\n")[0].replace(":", "").strip()

def parse_date(date_str):
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None

def is_recent(date_str, days_back):
    if days_back == 0: return True
    dt = parse_date(date_str)
    if dt is None: return True
    return dt >= datetime.now() - timedelta(days=days_back)

def score_item(ten, linh_vuc, keywords):
    text = f"{ten} {linh_vuc}".lower()
    score = 1
    tier5 = ["hạ tầng mạng", "an toàn thông tin", "chuyển đổi số", "cáp quang", "truyền dẫn", "bts", "trạm phát sóng", "tủ nguồn", "switch", "router"]
    tier4 = ["viễn thông", "sfp", "access point", "máy chủ", "server", "wifi", "camera"]
    for kw in tier5:
        if kw in text: score += 1.5
    for kw in tier4:
        if kw in text: score += 1.0
    for kw in keywords:
        if kw.lower() in text: score += 0.5
    return min(round(score), 5)

def fetch_bid_details(driver, url, wait):
    if url == "N/A": return "N/A", "N/A"
    driver.execute_script(f"window.open('{url}', '_blank');")
    driver.switch_to.window(driver.window_handles[1])
    gia_du_toan = "N/A"
    hinh_thuc = "N/A"
    try:
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "format-item")))
        page_text = driver.find_element(By.TAG_NAME, "body").text
        if "Giá dự toán gói thầu" in page_text:
            gia_du_toan = get_v("Giá dự toán gói thầu", page_text)
        elif "Giá gói thầu" in page_text:
            gia_du_toan = get_v("Giá gói thầu", page_text)
        hinh_thuc = get_v("Hình thức lựa chọn nhà thầu", page_text)
    except Exception:
        pass
    finally:
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
    return gia_du_toan, hinh_thuc

def get_ai_analysis(api_key, ten, linh_vuc, chu_dau_tu):
    if not api_key: return "Chưa cấu hình AI"
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Bạn là chuyên gia phân tích đấu thầu mảng Viễn thông / CNTT cho công ty MobiFone.
        Đánh giá độ tiềm năng của gói thầu sau (từ 1 đến 5 sao):
        - Tên gói: {ten}
        - Lĩnh vực: {linh_vuc}
        - Chủ đầu tư: {chu_dau_tu}
        
        Trả về ĐÚNG ĐỊNH DẠNG SAU:
        Điểm: [Số sao]⭐
        Phân tích: [Tóm tắt 1 câu ngắn gọn tại sao lại cho số điểm này]
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Lỗi AI: {e}"

def send_telegram(token, chat_id, message):
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def send_telegram_file(token, chat_id, caption, file_path):
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            requests.post(url, data=data, files=files, timeout=30)
    except: pass

# ==========================================
# CORE: QUÉT DỮ LIỆU TỪ MẠNG
# ==========================================
def run_scraper(gui_app):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key='app_config'")
    row = c.fetchone()
    config = json.loads(row[0]) if row else {}
        
    LIMIT_PAGES = config.get("LIMIT_PAGES", 200)
    DAYS_BACK = config.get("DAYS_BACK", 30)
    FETCH_DETAILS = config.get("FETCH_DETAILS", False)
    TG_TOKEN = config.get("TELEGRAM_BOT_TOKEN", "").strip()
    TG_CHAT_ID = config.get("TELEGRAM_CHAT_ID", "").strip()
    GEMINI_KEY = config.get("GEMINI_API_KEY", "").strip()
    
    kw_groups = config.get("KEYWORD_GROUPS", {})
    selected_groups = config.get("SELECTED_GROUPS", [])
    KEYWORDS = []
    for grp in selected_groups:
        if grp in kw_groups:
            KEYWORDS.extend(kw_groups[grp])
            
    gui_app.log("⚙️ Khởi tạo trình duyệt ẩn...")
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("window-size=1920,1080")
    options.add_argument("--log-level=3")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    
    wait = WebDriverWait(driver, 20)
    count_new_total = 0

    try:
        url = "https://muasamcong.mpi.gov.vn/web/guest/contractor-selection?render=index"
        gui_app.log("🚀 Đang cào dữ liệu mới từ Mua sắm công...")
        
        for attempt in range(3):
            try:
                driver.get(url)
                break
            except Exception as e:
                if attempt == 2: raise e
                gui_app.log(f"⚠️ Thử kết nối lại ({attempt + 1}/3)...")
                time.sleep(3)

        try:
            select_el = wait.until(EC.presence_of_element_located((By.XPATH, "//select[option[@value='50']]")))
            Select(select_el).select_by_value("50")
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "content__body__left__item")))
        except: pass

        try:
            page_nums = driver.find_elements(By.CSS_SELECTOR, "li.number")
            total_found = int(page_nums[-1].text) if page_nums else LIMIT_PAGES
            MAX_PAGE = min(total_found, LIMIT_PAGES)
        except: MAX_PAGE = LIMIT_PAGES

        skipped_old = 0
        skipped_dup = 0
        
        for page in range(1, MAX_PAGE + 1):
            gui_app.log(f"📄 Cào Trang {page}/{MAX_PAGE}...")
            gui_app.set_progress(page, MAX_PAGE)

            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "content__body__left__item")))
                time.sleep(1.5)
                items = driver.find_elements(By.CLASS_NAME, "content__body__left__item")
                count_added = 0

                for item in items:
                    try:
                        full_text = item.text
                        ma_tbmt = get_v("Mã TBMT", full_text)
                        
                        if is_scraped(conn, ma_tbmt):
                            skipped_dup += 1
                            continue

                        ngay_dang = get_v("Ngày đăng tải thông báo", full_text)
                        if DAYS_BACK > 0 and not is_recent(ngay_dang, DAYS_BACK):
                            skipped_old += 1
                            continue

                        try: link = item.find_element(By.TAG_NAME, "a").get_attribute("href") or "N/A"
                        except: link = "N/A"
                            
                        ten = get_v("Tên gói thầu", full_text)
                        if ten == "N/A":
                            try: ten = item.find_element(By.TAG_NAME, "h5").text
                            except: pass

                        linh_vuc = get_v("Lĩnh vực", full_text)
                        chu_dau_tu = get_v("Chủ đầu tư", full_text)
                        dia_diem = get_v("Địa điểm", full_text)
                        dong_thau = get_v("Thời điểm đóng thầu", full_text) if "Thời điểm đóng thầu" in full_text else get_v("Thời điểm bắt đầu chào giá trực tuyến", full_text)

                        gia_du_toan = "N/A"
                        hinh_thuc = "N/A"
                        item_score = score_item(ten, linh_vuc, KEYWORDS)
                        ai_summary = ""
                        
                        if item_score >= 3 and GEMINI_KEY:
                            ai_summary = get_ai_analysis(GEMINI_KEY, ten, linh_vuc, chu_dau_tu)
                        
                        if FETCH_DETAILS and item_score >= 2:
                            gia_du_toan, hinh_thuc = fetch_bid_details(driver, link, wait)
                            
                        if item_score >= 4 and TG_TOKEN and TG_CHAT_ID:
                            msg = f"🚨 <b>CÓ GÓI THẦU MỚI ({item_score}⭐)</b>\n\n"
                            msg += f"📦 <b>Tên gói:</b> {ten}\n"
                            msg += f"🏢 <b>Chủ đầu tư:</b> {chu_dau_tu}\n"
                            msg += f"💰 <b>Giá dự toán:</b> {gia_du_toan}\n"
                            msg += f"🤖 <b>AI Đánh giá:</b>\n<i>{ai_summary}</i>\n"
                            msg += f"🔗 <a href='{link}'>Xem chi tiết</a>"
                            send_telegram(TG_TOKEN, TG_CHAT_ID, msg)

                        data_dict = {
                            "Mã TBMT": ma_tbmt, "Tên gói thầu": ten, "Chủ đầu tư": chu_dau_tu,
                            "Lĩnh vực": linh_vuc, "Giá dự toán": gia_du_toan, "Hình thức LCNT": hinh_thuc,
                            "Ngày đăng": ngay_dang, "Đóng thầu": dong_thau, "Địa điểm": dia_diem,
                            "Link chi tiết": link, "Điểm": item_score, "AI Summary": ai_summary
                        }
                        
                        save_scraped_full(conn, data_dict)
                        count_added += 1
                        count_new_total += 1

                    except Exception: continue

                if page < MAX_PAGE:
                    for attempt in range(3):
                        try:
                            next_btn = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-next")))
                            driver.execute_script("arguments[0].click();", next_btn)
                            wait.until(EC.staleness_of(items[0]))
                            break
                        except:
                            if attempt == 2: MAX_PAGE = page
                            time.sleep(3)
            except: break
            
        gui_app.log(f"✅ Quét xong! Tìm thấy {count_new_total} gói mới (Bỏ qua {skipped_dup} trùng, {skipped_old} cũ).")
        
        # Nếu không có gói mới mà gọi từ scheduler, vẫn báo cáo
        if count_new_total == 0 and TG_TOKEN and TG_CHAT_ID:
            send_telegram(TG_TOKEN, TG_CHAT_ID, "💤 <b>BÁO CÁO ĐẤU THẦU</b>\nĐã quét xong nhưng không có gói thầu mới nào.")

    finally:
        driver.quit()
        conn.close()

# ==========================================
# EXPORT DATA TỪ SQLITE RA EXCEL
# ==========================================
def export_to_excel(gui_app, auto_send=False):
    gui_app.log("💾 Đang xuất file Excel từ CSDL...")
    conn = init_db()
    c = conn.cursor()
    
    # Đọc cấu hình để lấy DAYS_BACK
    c.execute("SELECT value FROM config WHERE key='app_config'")
    row = c.fetchone()
    config = json.loads(row[0]) if row else {}
    DAYS_BACK = config.get("DAYS_BACK", 30)
    TG_TOKEN = config.get("TELEGRAM_BOT_TOKEN", "").strip()
    TG_CHAT_ID = config.get("TELEGRAM_CHAT_ID", "").strip()

    # Lấy toàn bộ dữ liệu từ bảng bids_full
    df = pd.read_sql_query("SELECT * FROM bids_full", conn)
    conn.close()
    
    if df.empty:
        gui_app.log("❌ CSDL đang trống, chưa có gói thầu nào.")
        return

    # Chỉ lọc các gói trong vòng DAYS_BACK ngày
    def is_recent_row(date_str):
        if DAYS_BACK == 0: return True
        dt = parse_date(date_str)
        if dt is None: return True
        return dt >= datetime.now() - timedelta(days=DAYS_BACK)
        
    df['is_recent'] = df['ngay_dang'].apply(is_recent_row)
    df = df[df['is_recent']].drop(columns=['is_recent', 'ngay_quet'])
    
    # Định dạng lại tên cột cho Excel
    df = df.rename(columns={
        'ma_tbmt': 'Mã TBMT', 'ten': 'Tên gói thầu', 'chu_dau_tu': 'Chủ đầu tư',
        'linh_vuc': 'Lĩnh vực', 'gia_du_toan': 'Giá dự toán', 'hinh_thuc': 'Hình thức LCNT',
        'ngay_dang': 'Ngày đăng', 'dong_thau': 'Đóng thầu', 'dia_diem': 'Địa điểm',
        'link': 'Link chi tiết', 'diem_phu_hop': 'Điểm số'
    })

    # Lọc danh sách MobiFone (Điểm >= 3)
    df_mobi = df[df['Điểm số'] >= 3].copy()
    if not df_mobi.empty:
        df_mobi["Điểm phù hợp"] = df_mobi['Điểm số'].apply(lambda x: "⭐" * int(x))
        df_mobi = df_mobi.drop(columns=['Điểm số']).sort_values("Điểm phù hợp", ascending=False)
    
    df = df.drop(columns=['Điểm số'])

    os.makedirs("output", exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    file_name = os.path.join("output", f"muasamcong_mobifone_{date_str}.xlsx")

    with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Tất cả gói thầu", index=False)
        df_mobi.to_excel(writer, sheet_name="Gợi ý cho MobiFone", index=False)

    gui_app.log(f"✅ Đã xuất báo cáo: {file_name}")
    gui_app.log(f"📊 Tổng gói lấy được ({DAYS_BACK} ngày): {len(df)}")
    gui_app.log(f"📱 Gói tiềm năng: {len(df_mobi)}")
    
    if auto_send and TG_TOKEN and TG_CHAT_ID:
        gui_app.log("🚀 Đang gửi file báo cáo lên Telegram...")
        summary_msg = f"📊 <b>BÁO CÁO ĐẤU THẦU ({DAYS_BACK} NGÀY)</b>\n"
        summary_msg += f"✅ Cập nhật lúc: {datetime.now().strftime('%H:%M %d/%m/%Y')}\n"
        summary_msg += f"📦 Tổng số gói: {len(df)}\n"
        summary_msg += f"⭐ Gói tiềm năng: {len(df_mobi)}\n"
        send_telegram_file(TG_TOKEN, TG_CHAT_ID, summary_msg, file_name)
