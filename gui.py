import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import json
import os
import sys
import sqlite3
import time
from datetime import datetime

def get_db_connection():
    conn = sqlite3.connect("bids.db")
    conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
    return conn

def load_db_config():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key='app_config'")
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    
    # Fallback to default
    default_config = {
        "LIMIT_PAGES": 200,
        "DAYS_BACK": 30,
        "PAGE_WAIT": 6,
        "FETCH_DETAILS": False,
        "KEYWORD_GROUPS": {
            "NHÓM 1: Mặc định": ["viễn thông", "cáp quang"]
        },
        "SELECTED_GROUPS": ["NHÓM 1: Mặc định"],
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "AUTO_TIME": "08:00",
        "ENABLE_AUTO": False
    }
    
    # Migrate if exists
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                old = json.load(f)
                default_config.update(old)
        except: pass
        
    save_db_config(default_config)
    return default_config

def save_db_config(config_dict):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('app_config', ?)", 
                 (json.dumps(config_dict, ensure_ascii=False),))
    conn.commit()
    conn.close()

class BiddingToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Công Cụ Quét Dữ Liệu Mua Sắm Công - Tự Động Hóa")
        self.root.geometry("850x700")
        self.root.configure(padx=20, pady=20)
        
        self.config = load_db_config()
        self.group_vars = {}
        self.is_scraping = False
        
        self.create_widgets()
        
        # Start background scheduler thread
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()

    def create_widgets(self):
        ttk.Label(self.root, text="CẤU HÌNH QUÉT GÓI THẦU", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))
        
        # TOP FRAME
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", pady=5)
        
        # Left: Basic Settings
        basic_frame = ttk.LabelFrame(top_frame, text="Thông số kỹ thuật", padding=10)
        basic_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ttk.Label(basic_frame, text="Số trang tối đa:").grid(row=0, column=0, sticky="w", pady=5)
        self.var_pages = tk.IntVar(value=self.config.get("LIMIT_PAGES", 200))
        ttk.Entry(basic_frame, textvariable=self.var_pages, width=10).grid(row=0, column=1, sticky="w", padx=10)
        
        ttk.Label(basic_frame, text="Lấy gói đăng trong (ngày):").grid(row=1, column=0, sticky="w", pady=5)
        self.var_days = tk.IntVar(value=self.config.get("DAYS_BACK", 30))
        ttk.Entry(basic_frame, textvariable=self.var_days, width=10).grid(row=1, column=1, sticky="w", padx=10)
        
        self.var_details = tk.BooleanVar(value=self.config.get("FETCH_DETAILS", False))
        ttk.Checkbutton(basic_frame, text="Lấy [Giá dự toán] (chạy chậm hơn)", variable=self.var_details).grid(row=2, column=0, columnspan=2, sticky="w", pady=10)

        # Right: Keyword Groups
        self.kw_frame = ttk.LabelFrame(top_frame, text="Chọn Nhóm Từ khóa (Lọc gói thầu)", padding=10)
        self.kw_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        self.render_keyword_checkboxes()
        
        # MIDDLE FRAME: Telegram & Scheduler
        mid_frame = ttk.Frame(self.root)
        mid_frame.pack(fill="x", pady=5)
        
        # Telegram Setup
        tg_frame = ttk.LabelFrame(mid_frame, text="Thông báo Telegram (Nhận tin khi có thầu >=4 sao)", padding=10)
        tg_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ttk.Label(tg_frame, text="Bot Token:").grid(row=0, column=0, sticky="w", pady=2)
        self.var_tg_token = tk.StringVar(value=self.config.get("TELEGRAM_BOT_TOKEN", ""))
        ttk.Entry(tg_frame, textvariable=self.var_tg_token, width=25).grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(tg_frame, text="Chat ID:").grid(row=1, column=0, sticky="w", pady=2)
        self.var_tg_chat = tk.StringVar(value=self.config.get("TELEGRAM_CHAT_ID", ""))
        ttk.Entry(tg_frame, textvariable=self.var_tg_chat, width=25).grid(row=1, column=1, sticky="w", padx=5)
        
        # Scheduler Setup
        sch_frame = ttk.LabelFrame(mid_frame, text="Lập lịch tự động (Treo máy)", padding=10)
        sch_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        self.var_auto_enable = tk.BooleanVar(value=self.config.get("ENABLE_AUTO", False))
        ttk.Checkbutton(sch_frame, text="Tự động quét mỗi ngày lúc:", variable=self.var_auto_enable).grid(row=0, column=0, sticky="w", pady=5)
        
        self.var_auto_time = tk.StringVar(value=self.config.get("AUTO_TIME", "08:00"))
        ttk.Entry(sch_frame, textvariable=self.var_auto_time, width=10).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(sch_frame, text="(Định dạng HH:MM, VD: 08:30)", font=("Segoe UI", 8)).grid(row=1, column=0, columnspan=2, sticky="w")

        # Action Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", pady=15)
        
        self.btn_save = ttk.Button(btn_frame, text="Lưu Cấu Hình", command=self.save_config_with_msg)
        self.btn_save.pack(side="left", padx=5)
        
        self.btn_manage = ttk.Button(btn_frame, text="⚙️ Quản lý Từ khóa", command=self.open_keyword_manager)
        self.btn_manage.pack(side="left", padx=5)
        
        self.btn_export = ttk.Button(btn_frame, text="📥 XUẤT EXCEL", command=self.export_excel, style="Accent.TButton")
        self.btn_export.pack(side="right", padx=5)
        
        self.btn_start = ttk.Button(btn_frame, text="▶ QUÉT MẠNG", command=lambda: self.start_scraping(False))
        self.btn_start.pack(side="right", padx=5)
        
        # Progress & Logs
        ttk.Label(self.root, text="Tiến trình:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(5, 0))
        
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x", pady=5)
        
        self.log_text = tk.Text(self.root, height=12, state="disabled", bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, pady=5)
        
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), foreground="green")

    def render_keyword_checkboxes(self):
        for widget in self.kw_frame.winfo_children():
            widget.destroy()
            
        kw_groups = self.config.get("KEYWORD_GROUPS", {})
        selected_groups = self.config.get("SELECTED_GROUPS", [])
        
        self.group_vars = {}
        row_idx = 0
        for group_name in kw_groups.keys():
            var = tk.BooleanVar(value=(group_name in selected_groups))
            self.group_vars[group_name] = var
            ttk.Checkbutton(self.kw_frame, text=group_name, variable=var).grid(row=row_idx, column=0, sticky="w", pady=2)
            row_idx += 1
            
        if not kw_groups:
            ttk.Label(self.kw_frame, text="Chưa có cấu hình nhóm từ khóa.").grid(row=0, column=0)

    def open_keyword_manager(self):
        top = tk.Toplevel(self.root)
        top.title("Quản lý Từ khóa")
        top.geometry("650x500")
        top.grab_set()
        top.configure(padx=20, pady=20)
        
        ttk.Label(top, text="Chọn Nhóm:").pack(anchor="w", pady=(0, 5))
        
        frame_top = ttk.Frame(top)
        frame_top.pack(fill="x", pady=5)
        
        cb_groups = ttk.Combobox(frame_top, state="readonly", width=40)
        cb_groups.pack(side="left", padx=(0,10))
        
        text_kws = tk.Text(top, height=15)
        
        def refresh_combobox(select_group=None):
            groups = list(self.config.get("KEYWORD_GROUPS", {}).keys())
            cb_groups["values"] = groups
            if groups:
                if select_group and select_group in groups:
                    cb_groups.set(select_group)
                else:
                    cb_groups.current(0)
                on_group_select(None)
            else:
                cb_groups.set('')
                text_kws.delete(1.0, "end")

        def on_group_select(event):
            grp = cb_groups.get()
            if not grp: return
            kws = self.config["KEYWORD_GROUPS"].get(grp, [])
            text_kws.delete(1.0, "end")
            text_kws.insert("end", ", ".join(kws))
            
        cb_groups.bind("<<ComboboxSelected>>", on_group_select)
        
        def save_current_group():
            grp = cb_groups.get()
            if not grp: return
            raw_text = text_kws.get(1.0, "end").strip()
            kws = [k.strip() for k in raw_text.split(",") if k.strip()]
            self.config["KEYWORD_GROUPS"][grp] = kws
            self.save_config()
            self.render_keyword_checkboxes()
            messagebox.showinfo("Thành công", f"Đã lưu {len(kws)} từ khóa cho nhóm '{grp}'", parent=top)
            
        def add_new_group():
            new_grp = simpledialog.askstring("Nhóm mới", "Nhập tên Nhóm từ khóa mới:", parent=top)
            if new_grp:
                new_grp = new_grp.strip()
                if new_grp in self.config.get("KEYWORD_GROUPS", {}):
                    messagebox.showerror("Lỗi", "Tên nhóm đã tồn tại!", parent=top)
                    return
                if "KEYWORD_GROUPS" not in self.config:
                    self.config["KEYWORD_GROUPS"] = {}
                self.config["KEYWORD_GROUPS"][new_grp] = []
                if new_grp not in self.config.get("SELECTED_GROUPS", []):
                    self.config.setdefault("SELECTED_GROUPS", []).append(new_grp)
                
                self.save_config()
                self.render_keyword_checkboxes()
                refresh_combobox(new_grp)
                messagebox.showinfo("Thành công", f"Đã thêm nhóm '{new_grp}'. Bạn có thể nhập từ khóa ở bên dưới.", parent=top)

        btn_save_grp = ttk.Button(frame_top, text="Lưu Nhóm Này", command=save_current_group)
        btn_save_grp.pack(side="left", padx=5)
        
        btn_add_grp = ttk.Button(frame_top, text="+ Thêm Nhóm Mới", command=add_new_group)
        btn_add_grp.pack(side="left", padx=5)
        
        ttk.Label(top, text="Danh sách từ khóa (cách nhau bởi dấu phẩy):").pack(anchor="w", pady=(15, 5))
        text_kws.pack(fill="both", expand=True, pady=5)
        
        refresh_combobox()

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def set_progress(self, current, total):
        if total > 0:
            pct = (current / total) * 100
            self.progress_var.set(pct)

    def save_config(self):
        self.config["LIMIT_PAGES"] = self.var_pages.get()
        self.config["DAYS_BACK"] = self.var_days.get()
        self.config["FETCH_DETAILS"] = self.var_details.get()
        self.config["TELEGRAM_BOT_TOKEN"] = self.var_tg_token.get()
        self.config["TELEGRAM_CHAT_ID"] = self.var_tg_chat.get()
        self.config["ENABLE_AUTO"] = self.var_auto_enable.get()
        self.config["AUTO_TIME"] = self.var_auto_time.get()
        
        selected = [g for g, v in self.group_vars.items() if v.get()]
        self.config["SELECTED_GROUPS"] = selected
        
        save_db_config(self.config)

    def save_config_with_msg(self):
        self.save_config()
        messagebox.showinfo("Thành công", "Đã lưu cấu hình!")

    def export_excel(self):
        if self.is_scraping: return
        self.save_config()
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")
        
        import scraper_core
        threading.Thread(target=lambda: scraper_core.export_to_excel(self, auto_send=False), daemon=True).start()

    def start_scraping(self, is_auto=False):
        if self.is_scraping: return
        self.save_config()
        if not self.config["SELECTED_GROUPS"]:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 nhóm từ khóa để quét!")
            return
            
        self.btn_start.config(state="disabled")
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")
        self.progress_var.set(0)
        self.is_scraping = True
        
        self.log("Đang khởi động tiến trình quét...")
        
        import scraper_core
        threading.Thread(target=self._run_thread, args=(is_auto,), daemon=True).start()
        
    def _run_thread(self, is_auto):
        import scraper_core
        try:
            scraper_core.run_scraper(self)
            self.log("\nHOÀN THÀNH QUÉT MẠNG!")
            if is_auto:
                scraper_core.export_to_excel(self, auto_send=True)
        except Exception as e:
            self.log(f"\nLỖI: {str(e)}")
        finally:
            self.is_scraping = False
            self.root.after(0, lambda: self.btn_start.config(state="normal"))
            
    def _scheduler_loop(self):
        while True:
            time.sleep(30)
            if self.is_scraping: continue
            
            # Check config directly
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
                        if now_time == target_time:
                            # Start scraping automatically
                            self.root.after(0, lambda: self.start_scraping(is_auto=True))
                            # Sleep for 61 seconds to avoid triggering multiple times in the same minute
                            time.sleep(61)
            except Exception:
                pass

if __name__ == "__main__":
    root = tk.Tk()
    app = BiddingToolGUI(root)
    root.mainloop()
