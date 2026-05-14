import streamlit as st
import pandas as pd
import sqlite3
import re
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# Cấu hình trang
st.set_page_config(page_title="Đấu Thầu Analytics Pro", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

# Thêm CSS tùy chỉnh cho giao diện đẹp hơn
st.markdown("""
<style>
    .metric-card {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        border-left: 5px solid #00C4B5;
        color: white;
    }
    .metric-title {
        font-size: 14px;
        color: #A0AEC0;
        text-transform: uppercase;
        font-weight: 600;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 32px;
        font-weight: bold;
        margin-bottom: 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        gap: 10px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(0, 196, 181, 0.1);
        border-bottom: 3px solid #00C4B5;
    }
</style>
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_keyword_groups():
    import json
    import os
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            try:
                config = json.load(f)
                return config.get("KEYWORD_GROUPS", {})
            except:
                pass
    return {}

@st.cache_data(ttl=300) # Cache 5 phút
def load_data():
    conn = sqlite3.connect("bids.db")
    try:
        df = pd.read_sql_query("SELECT * FROM bids_full", conn)
        # Parse Ngày đăng to datetime for filtering (Bỏ format cứng để Pandas tự linh hoạt)
        df['Ngày_Date'] = pd.to_datetime(df['ngay_dang'], dayfirst=True, errors='coerce')
        # Xóa các dòng rỗng
        df = df.dropna(subset=['ma_tbmt'])
        
        # Hàm chuẩn hóa Giá dự toán
        def parse_price(price_str):
            if not isinstance(price_str, str) or price_str == "N/A" or price_str == "": return 0
            clean_str = re.sub(r'[^\d,\.]', '', price_str)
            if ',' in clean_str and '.' in clean_str:
                if clean_str.rfind(',') > clean_str.rfind('.'): clean_str = clean_str.replace('.', '').replace(',', '.')
                else: clean_str = clean_str.replace(',', '')
            elif '.' in clean_str:
                if clean_str.count('.') > 1 or len(clean_str) - clean_str.rfind('.') == 4: clean_str = clean_str.replace('.', '')
            elif ',' in clean_str:
                if clean_str.count(',') > 1 or len(clean_str) - clean_str.rfind(',') == 4: clean_str = clean_str.replace(',', '')
                else: clean_str = clean_str.replace(',', '.')
            try: return float(clean_str)
            except: return 0
            
        df['Giá_Số'] = df['gia_du_toan'].apply(parse_price)
        
        # Phân loại nhóm hàng theo config - Tối ưu hóa bằng Vectorization
        kw_groups = load_keyword_groups()
        if kw_groups:
            df['Nhóm hàng'] = ""
            search_text = (df['ten'].fillna('') + ' ' + df['linh_vuc'].fillna('')).str.lower()
            
            for grp, kws in kw_groups.items():
                if not kws: continue
                short_name = grp.split(":", 1)[1].strip() if ":" in grp else grp
                pattern = '|'.join([re.escape(kw.lower()) for kw in kws])
                
                # Tìm các dòng match pattern này bằng C engine
                mask = search_text.str.contains(pattern, case=False, na=False, regex=True)
                
                # Thêm short_name vào các dòng match (xử lý dấu phẩy)
                mask_empty = mask & (df['Nhóm hàng'] == "")
                mask_not_empty = mask & (df['Nhóm hàng'] != "")
                
                df.loc[mask_empty, 'Nhóm hàng'] = short_name
                df.loc[mask_not_empty, 'Nhóm hàng'] += ", " + short_name
                
            df.loc[df['Nhóm hàng'] == "", 'Nhóm hàng'] = "Khác"
        else:
            df['Nhóm hàng'] = "Khác"
        
    except Exception as e:
        df = pd.DataFrame()
    conn.close()
    return df

def load_app_config():
    import json
    conn = sqlite3.connect("bids.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("SELECT value FROM config WHERE key='app_config'")
    row = c.fetchone()
    conn.close()
    if row:
        try: return json.loads(row[0])
        except: return {}
    return {}

def save_app_config(config_dict):
    import json
    conn = sqlite3.connect("bids.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("SELECT value FROM config WHERE key='app_config'")
    row = c.fetchone()
    old_config = {}
    if row:
        try: old_config = json.loads(row[0])
        except: pass
    
    old_config.update(config_dict)
    c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('app_config', ?)", (json.dumps(old_config),))
    conn.commit()
    conn.close()

st.title("📈 Báo cáo Trí tuệ Đấu Thầu (BI Dashboard)")
st.markdown("Hệ thống tự động phân tích dữ liệu đấu thầu trực tuyến kết hợp Google Gemini AI.")

df = load_data()

if df.empty:
    st.warning("CSDL hiện chưa có dữ liệu. Vui lòng đợi tiến trình cào dữ liệu hoàn tất.")
    st.stop()

# Đổi tên cột cho đẹp
df = df.rename(columns={
    'ma_tbmt': 'Mã TBMT', 'ten': 'Tên gói thầu', 'chu_dau_tu': 'Chủ đầu tư',
    'linh_vuc': 'Lĩnh vực', 'gia_du_toan': 'Giá dự toán', 'hinh_thuc': 'Hình thức LCNT',
    'ngay_dang': 'Ngày đăng', 'dong_thau': 'Đóng thầu', 'dia_diem': 'Địa điểm',
    'link': 'Link chi tiết', 'diem_phu_hop': 'Điểm số', 'ai_summary': 'AI Đánh giá'
})

kw_groups_dict = load_keyword_groups()

# ==========================================
# SIDEBAR LỌC DỮ LIỆU
# ==========================================
st.sidebar.header("🔍 CÔNG CỤ LỌC")

# 1. Lọc theo Từ khóa
search_text = st.sidebar.text_input("Tìm kiếm (Mã, Tên, CĐT):", placeholder="Ví dụ: Mobifone...")

# 1.5 Lọc theo Nhà mạng & 34 Tỉnh thành (Cập nhật 2025)
st.sidebar.markdown("**🏢 Lọc Chủ đầu tư (Telco):**")
TELCOS = ["Tất cả", "Viettel", "MobiFone", "VNPT"]
PROVINCES_34 = [
    "Hà Nội", "Huế", "Quảng Ninh", "Cao Bằng", "Lạng Sơn", "Lai Châu", 
    "Điện Biên", "Sơn La", "Thanh Hóa", "Nghệ An", "Hà Tĩnh", 
    "Tuyên Quang", "Lào Cai", "Thái Nguyên", "Phú Thọ", "Bắc Ninh", 
    "Hải Phòng", "Ninh Bình", "Quảng Trị", "Đà Nẵng", "Quảng Ngãi", 
    "Gia Lai", "Khánh Hòa", "Lâm Đồng", "Đắk Lắk", "Hồ Chí Minh", 
    "Đồng Nai", "Tây Ninh", "Cần Thơ", "Đồng Tháp", "Vĩnh Long", 
    "Cà Mau", "An Giang", "Kiên Giang"
]
selected_telco = st.sidebar.selectbox("Nhà mạng:", TELCOS)
selected_provinces = st.sidebar.multiselect("Tỉnh/Thành (34 tỉnh sáp nhập):", options=PROVINCES_34)

# 2. Lọc theo Khoảng thời gian
today_date = datetime.today().date()
min_dt = df['Ngày_Date'].min()
max_dt = df['Ngày_Date'].max()

min_date = min_dt.date() if pd.notna(min_dt) else today_date
max_date = max_dt.date() if pd.notna(max_dt) else today_date

# Fix lỗi parse ngày của Pandas nếu cào trúng dữ liệu rác (Ví dụ năm 6051)
if min_date.year < 2020: min_date = datetime(2020, 1, 1).date()
if max_date.year > today_date.year + 1: max_date = today_date
if min_date > max_date: min_date = max_date

# Bộ lọc ngày thông minh: Tách làm 3 tùy chọn
st.sidebar.markdown("**📅 Khoảng thời gian:**")
date_preset = st.sidebar.selectbox("Chọn nhanh:", ["Tất cả", "Hôm nay", "7 ngày qua", "30 ngày qua", "Tùy chọn (Từ ngày - Đến ngày)"])

if date_preset == "Tất cả":
    start_d = min_date
    end_d = max_date
elif date_preset == "Hôm nay":
    start_d = today_date
    end_d = today_date
elif date_preset == "7 ngày qua":
    start_d = today_date - timedelta(days=7)
    end_d = today_date
elif date_preset == "30 ngày qua":
    start_d = today_date - timedelta(days=30)
    end_d = today_date
else:
    # Tùy chọn riêng biệt 2 ô
    c1, c2 = st.sidebar.columns(2)
    with c1:
        start_d = st.date_input("Từ ngày:", value=min_date, min_value=datetime(2020, 1, 1).date(), max_value=today_date + timedelta(days=30))
    with c2:
        end_d = st.date_input("Đến ngày:", value=max_date, min_value=datetime(2020, 1, 1).date(), max_value=today_date + timedelta(days=30))

# 3. Lọc theo Điểm số
min_score = st.sidebar.slider("Độ tiềm năng (Từ bao nhiêu sao):", 0, 5, 0)

# 4. Lọc theo Nhóm thiết bị (Từ config.json)
if kw_groups_dict:
    st.sidebar.markdown("**📦 Lọc theo Nhóm thiết bị:**")
    all_groups = [grp.split(":", 1)[1].strip() if ":" in grp else grp for grp in kw_groups_dict.keys()]
    all_groups.append("Khác")
    selected_groups_filter = st.sidebar.multiselect("Nhóm hàng:", options=all_groups, default=[])

# 5. Lọc theo Lĩnh vực
all_fields = df['Lĩnh vực'].dropna().unique().tolist()
selected_fields = st.sidebar.multiselect("Lĩnh vực (Gốc):", options=all_fields, default=all_fields)

st.sidebar.divider()
st.sidebar.caption("💡 Mẹo: Nhấn 'R' trên bàn phím để tải lại dữ liệu mới nhất.")

# Xử lý lọc Dataframe
filtered_df = df[df['Điểm số'] >= min_score]

start_dt = pd.to_datetime(start_d)
end_dt = pd.to_datetime(end_d) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
filtered_df = filtered_df[(filtered_df['Ngày_Date'] >= start_dt) & (filtered_df['Ngày_Date'] <= end_dt)]

if selected_fields:
    filtered_df = filtered_df[filtered_df['Lĩnh vực'].isin(selected_fields)]

if kw_groups_dict and selected_groups_filter:
    # Check if any of the selected groups is in the "Nhóm hàng" column
    pattern = '|'.join([re.escape(grp) for grp in selected_groups_filter])
    filtered_df = filtered_df[filtered_df['Nhóm hàng'].str.contains(pattern, case=False, na=False)]

if selected_telco != "Tất cả":
    if selected_telco == "MobiFone":
        filtered_df = filtered_df[filtered_df['Chủ đầu tư'].str.contains(r'mobi', case=False, na=False)]
    else:
        filtered_df = filtered_df[filtered_df['Chủ đầu tư'].str.contains(selected_telco, case=False, na=False)]

if selected_provinces:
    pattern = '|'.join(selected_provinces)
    filtered_df = filtered_df[
        filtered_df['Chủ đầu tư'].str.contains(pattern, case=False, na=False) |
        filtered_df['Tên gói thầu'].str.contains(pattern, case=False, na=False) |
        filtered_df['Địa điểm'].str.contains(pattern, case=False, na=False)
    ]

if search_text:
    search_term = search_text.lower()
    filtered_df = filtered_df[
        filtered_df['Tên gói thầu'].str.lower().str.contains(search_term, na=False) |
        filtered_df['Chủ đầu tư'].str.lower().str.contains(search_term, na=False) |
        filtered_df['Mã TBMT'].str.lower().str.contains(search_term, na=False)
    ]

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 TỔNG QUAN", "🔍 DỮ LIỆU GÓI THẦU", "🤖 AI TRỢ LÝ", "🕵️ TÌNH BÁO ĐỐI THỦ", "⚙️ CÀI ĐẶT HỆ THỐNG"])

with tab1:
    # --- KPIs ---
    col1, col2, col3, col4 = st.columns(4)
    total_bids = len(filtered_df)
    potential_bids = len(filtered_df[filtered_df['Điểm số'] >= 3])
    top_bids = len(filtered_df[filtered_df['Điểm số'] >= 4])
    ai_analyzed = len(filtered_df[filtered_df['AI Đánh giá'].str.len() > 5])
    
    col1.markdown(f'<div class="metric-card"><div class="metric-title">Tổng số Gói thầu</div><div class="metric-value">{total_bids}</div></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="metric-card" style="border-left-color: #F6AD55;"><div class="metric-title">Gói Tiềm năng (≥3⭐)</div><div class="metric-value">{potential_bids}</div></div>', unsafe_allow_html=True)
    col3.markdown(f'<div class="metric-card" style="border-left-color: #F56565;"><div class="metric-title">Gói Trọng điểm (≥4⭐)</div><div class="metric-value">{top_bids}</div></div>', unsafe_allow_html=True)
    col4.markdown(f'<div class="metric-card" style="border-left-color: #9F7AEA;"><div class="metric-title">Đã được AI Phân tích</div><div class="metric-value">{ai_analyzed}</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- Biểu đồ ---
    if not filtered_df.empty:
        c1, c2 = st.columns([6, 4])
        
        with c1:
            # Lưu lượng đăng tải
            st.subheader("Xu hướng Đăng tải")
            date_counts = filtered_df['Ngày_Date'].dt.date.value_counts().reset_index()
            date_counts.columns = ['Ngày', 'Số lượng']
            date_counts = date_counts.sort_values('Ngày')
            fig_line = px.area(date_counts, x='Ngày', y='Số lượng', template="plotly_dark", 
                              color_discrete_sequence=['#00C4B5'])
            fig_line.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=350)
            sel_line = st.plotly_chart(fig_line, use_container_width=True, on_select="rerun")
            
        with c2:
            # Phân bổ Lĩnh vực
            st.subheader("Cơ cấu Lĩnh vực")
            field_counts = filtered_df['Lĩnh vực'].value_counts().reset_index()
            field_counts.columns = ['Lĩnh vực', 'Số lượng']
            fig_pie = px.pie(field_counts, values='Số lượng', names='Lĩnh vực', hole=0.4, 
                             template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=350)
            sel_pie = st.plotly_chart(fig_pie, use_container_width=True, on_select="rerun")
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Bảng xếp hạng Chủ đầu tư
        st.subheader("Top 10 Chủ đầu tư Sôi động nhất")
        investor_counts = filtered_df['Chủ đầu tư'].value_counts().head(10).reset_index()
        investor_counts.columns = ['Chủ đầu tư', 'Số lượng']
        investor_counts = investor_counts.sort_values('Số lượng', ascending=True)
        fig_bar = px.bar(investor_counts, x='Số lượng', y='Chủ đầu tư', orientation='h',
                         template="plotly_dark", text_auto=True, color_discrete_sequence=['#F6AD55'])
        fig_bar.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=400)
        sel_bar = st.plotly_chart(fig_bar, use_container_width=True, on_select="rerun")
        
        # --- XỬ LÝ SỰ KIỆN CLICK BIỂU ĐỒ ---
        def get_pt(sel):
            try:
                pts = sel.get("selection", {}).get("points", [])
                return pts[0] if pts else {}
            except:
                try: return sel.selection.points[0] if getattr(sel, 'selection', None) and sel.selection.points else {}
                except: return {}

        pt_line = get_pt(sel_line)
        pt_pie = get_pt(sel_pie)
        pt_bar = get_pt(sel_bar)
        
        click_df = None
        filter_title = ""
        
        if pt_line and 'x' in pt_line:
            # Click Area chart
            clicked_date = pt_line['x']
            filter_title = f"Gói thầu đăng ngày: {clicked_date}"
            # Cần convert clicked_date string về date object để so sánh với Ngày_Date (datetime)
            # Tuy nhiên, trong Pandas, so sánh chuỗi YYYY-MM-DD với datetime cũng hoạt động
            click_df = filtered_df[filtered_df['Ngày_Date'].astype(str).str.startswith(clicked_date)]
            
        elif pt_pie and ('label' in pt_pie or 'x' in pt_pie):
            # Click Pie chart
            clicked_field = pt_pie.get('label', pt_pie.get('x'))
            filter_title = f"Gói thầu mảng: {clicked_field}"
            click_df = filtered_df[filtered_df['Lĩnh vực'] == clicked_field]
            
        elif pt_bar and 'y' in pt_bar:
            # Click Bar chart
            clicked_investor = pt_bar['y']
            filter_title = f"Gói thầu của Chủ đầu tư: {clicked_investor}"
            click_df = filtered_df[filtered_df['Chủ đầu tư'] == clicked_investor]
            
        if click_df is not None and not click_df.empty:
            st.markdown("---")
            st.subheader(f"👇 Bảng dữ liệu tương tác: {filter_title}")
            display_cols = ['Mã TBMT', 'Tên gói thầu', 'Chủ đầu tư', 'Nhóm hàng', 'Giá dự toán', 'Ngày đăng', 'Điểm số', 'Link chi tiết']
            st.dataframe(
                click_df[display_cols],
                column_config={
                    "Link chi tiết": st.column_config.LinkColumn(
                        "Đường dẫn",
                        help="Nhấn để mở trang web Mua sắm công",
                        display_text="🌐 Xem Hồ Sơ"
                    )
                },
                use_container_width=True, hide_index=True
            )
    else:
        st.info("Không có dữ liệu để vẽ biểu đồ theo bộ lọc hiện tại.")

with tab2:
    col_a, col_b = st.columns([8, 2])
    with col_a:
        st.subheader(f"Danh sách chi tiết ({len(filtered_df)} gói)")
    with col_b:
        # Nút xuất CSV
        @st.cache_data
        def convert_df(df):
            return df.to_csv(index=False).encode('utf-8')
        
        csv = convert_df(filtered_df.drop(columns=['Ngày_Date']))
        st.download_button("📥 Tải Xuống CSV", data=csv, file_name="du_lieu_dau_thau.csv", mime="text/csv", use_container_width=True)
    
    # Bảng dữ liệu tương tác
    display_cols = ['Mã TBMT', 'Tên gói thầu', 'Chủ đầu tư', 'Nhóm hàng', 'Lĩnh vực', 'Giá dự toán', 'Ngày đăng', 'Điểm số', 'Link chi tiết']
    if not filtered_df.empty:
        st.dataframe(
            filtered_df[display_cols],
            column_config={
                "Link chi tiết": st.column_config.LinkColumn(
                    "Đường dẫn",
                    help="Nhấn để mở trang web Mua sắm công",
                    display_text="🌐 Xem Hồ Sơ"
                )
            },
            use_container_width=True, 
            hide_index=True,
            height=600
        )
    else:
        st.info("Không tìm thấy kết quả nào.")

with tab3:
    st.subheader("Báo cáo Phân tích từ Google Gemini 🧠")
    st.markdown("Chỉ hiển thị các gói thầu tiềm năng có điểm số cao và đã được AI đọc hiểu hồ sơ.")
    
    if 'AI Đánh giá' not in filtered_df.columns:
        st.warning("Hệ thống chưa có dữ liệu AI. Hãy kiểm tra cấu hình Gemini API Key.")
    else:
        # Chỉ lấy gói có AI
        ai_df = filtered_df[filtered_df['AI Đánh giá'].notna() & (filtered_df['AI Đánh giá'] != "")]
        
        if ai_df.empty:
            st.info("Không có nhận xét AI nào cho dữ liệu đang lọc.")
        else:
            # Sắp xếp theo điểm số cao nhất lên đầu
            ai_df = ai_df.sort_values(by='Điểm số', ascending=False)
            
            # Chia thành 2 cột cho đẹp
            col_l, col_r = st.columns(2)
            
            for idx, row in enumerate(ai_df.itertuples()):
                # Phân bổ chéo cột trái phải
                target_col = col_l if idx % 2 == 0 else col_r
                
                with target_col:
                    stars = "⭐" * int(row._12) # row._12 is Điểm số (index varies, better to use getattr)
                    # Use index via dictionary to be safe
                    row_dict = row._asdict()
                    score = row_dict['Điểm_số']
                    stars = "⭐" * int(score) if score > 0 else ""
                    
                    with st.expander(f"{stars} [{row_dict['Mã_TBMT']}] - {row_dict['Tên_gói_thầu'][:60]}..."):
                        st.markdown(f"**🏢 Chủ đầu tư:** {row_dict['Chủ_đầu_tư']}")
                        st.markdown(f"**💰 Giá dự toán:** {row_dict['Giá_dự_toán']}")
                        st.markdown(f"**📅 Đóng thầu:** {row_dict['Đóng_thầu']}")
                        
                        st.markdown("---")
                        st.markdown(f"🤖 **AI Nhận xét:**\n> {row_dict['AI_Đánh_giá']}")
                        
                        st.markdown(f"[🔗 Nhấn vào đây để xem Hồ sơ gốc trên Mua sắm công]({row_dict['Link_chi_tiết']})")

with tab4:
    st.subheader("🕵️ Hồ sơ Năng lực / Phân tích Đối thủ")
    st.markdown("Nhập tên tổ chức (Công ty đối thủ hoặc Chủ đầu tư) để trích xuất toàn bộ dữ liệu từ kho Data Warehouse nội bộ.")
    
    col_search, col_btn = st.columns([8, 2])
    with col_search:
        target_name = st.text_input("Tên Tổ chức cần phân tích:", placeholder="VD: Bệnh viện Nhi đồng, VNPT, Mobifone...")
    
    if target_name:
        # Lọc dữ liệu KHÔNG phụ thuộc vào bộ lọc sidebar (lấy toàn bộ DB)
        comp_df = df[
            df['Chủ đầu tư'].str.lower().str.contains(target_name.lower(), na=False) |
            df['Tên gói thầu'].str.lower().str.contains(target_name.lower(), na=False)
        ]
        
        if comp_df.empty:
            st.warning(f"Không tìm thấy dữ liệu nào liên quan đến '{target_name}' trong Data Warehouse.")
        else:
            st.success(f"Đã tìm thấy **{len(comp_df)}** gói thầu liên quan đến '{target_name}'.")
            
            # --- Tính KPIs cho Đối thủ ---
            c1, c2, c3 = st.columns(3)
            total_packages = len(comp_df)
            total_budget = comp_df['Giá_Số'].sum()
            
            # Định dạng tỷ đồng
            if total_budget > 1e9: budget_str = f"{total_budget / 1e9:.2f} Tỷ VNĐ"
            elif total_budget > 1e6: budget_str = f"{total_budget / 1e6:.2f} Triệu VNĐ"
            else: budget_str = f"{total_budget:,.0f} VNĐ"
            
            most_freq_field = comp_df['Lĩnh vực'].mode()[0] if not comp_df['Lĩnh vực'].empty else "N/A"
            
            c1.markdown(f'<div class="metric-card" style="border-left-color: #E53E3E;"><div class="metric-title">Số lần xuất hiện</div><div class="metric-value">{total_packages} gói</div></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="metric-card" style="border-left-color: #38A169;"><div class="metric-title">Ước tính Ngân sách (Tổng)</div><div class="metric-value">{budget_str}</div></div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="metric-card" style="border-left-color: #3182CE;"><div class="metric-title">Sở trường / Lĩnh vực chính</div><div class="metric-value" style="font-size: 20px;">{most_freq_field}</div></div>', unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- Biểu đồ phân tích đối thủ ---
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                # 1. Radar Chart phân bổ lĩnh vực (Khẩu vị đấu thầu)
                radar_data = comp_df['Lĩnh vực'].value_counts().reset_index()
                radar_data.columns = ['Lĩnh vực', 'Số lượng']
                fig_radar = px.line_polar(radar_data, r='Số lượng', theta='Lĩnh vực', line_close=True,
                                          title="Mạng nhện Khẩu vị Đấu thầu",
                                          template="plotly_dark", color_discrete_sequence=['#ED8936'])
                fig_radar.update_traces(fill='toself')
                fig_radar.update_layout(margin=dict(l=40, r=40, t=40, b=40))
                st.plotly_chart(fig_radar, use_container_width=True)
                
            with col_chart2:
                # 2. Biểu đồ hình thức LCNT
                hinh_thuc_data = comp_df['Hình thức LCNT'].value_counts().reset_index()
                hinh_thuc_data.columns = ['Hình thức', 'Số lượng']
                fig_ht = px.pie(hinh_thuc_data, values='Số lượng', names='Hình thức', hole=0.5,
                                title="Phân bổ Hình thức Đấu thầu", template="plotly_dark",
                                color_discrete_sequence=px.colors.qualitative.Set3)
                fig_ht.update_layout(margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_ht, use_container_width=True)
                
            st.subheader("Lịch sử Đấu thầu chi tiết")
            st.dataframe(
                comp_df[['Mã TBMT', 'Tên gói thầu', 'Chủ đầu tư', 'Lĩnh vực', 'Giá dự toán', 'Ngày đăng', 'Link chi tiết']],
                column_config={
                    "Link chi tiết": st.column_config.LinkColumn(
                        "Đường dẫn",
                        help="Nhấn để mở trang web Mua sắm công",
                        display_text="🌐 Xem Hồ Sơ"
                    )
                },
                use_container_width=True, hide_index=True
            )

with tab5:
    st.subheader("⚙️ Cài đặt Hệ thống & Thông báo")
    st.markdown("Quản lý khóa bảo mật API và kết nối với Bot Telegram. Dữ liệu được lưu an toàn trên máy chủ.")
    
    config = load_app_config()
    current_token = config.get("TELEGRAM_TOKEN", "")
    current_chat_id = str(config.get("TELEGRAM_CHAT_ID", ""))
    current_gemini = config.get("GEMINI_API_KEY", "")
    
    with st.form("settings_form"):
        st.markdown("### 📱 Cấu hình Telegram Bot")
        st.info("Để nhận thông báo gói thầu mới, bạn cần tạo Bot từ @BotFather và lấy Token.")
        
        telegram_token = st.text_input("Telegram Bot Token:", value=current_token, type="password", 
                                       help="Mã Token API lấy từ @BotFather")
        telegram_chat_id = st.text_input("Telegram Chat ID:", value=current_chat_id, 
                                         help="Lấy từ @userinfobot (Có thể là ID cá nhân hoặc Group)")
        
        st.markdown("### 🧠 Cấu hình Trí tuệ Nhân tạo (Google Gemini)")
        gemini_api_key = st.text_input("Gemini API Key:", value=current_gemini, type="password",
                                       help="Lấy từ Google AI Studio")
        
        submitted = st.form_submit_button("LƯU CẤU HÌNH", use_container_width=True, type="primary")
        if submitted:
            cleaned_token = telegram_token.strip()
            if cleaned_token.lower().startswith("bot"):
                cleaned_token = cleaned_token[3:]
                
            new_config = {
                "TELEGRAM_TOKEN": cleaned_token,
                "TELEGRAM_CHAT_ID": telegram_chat_id.strip(),
                "GEMINI_API_KEY": gemini_api_key.strip()
            }
            save_app_config(new_config)
            st.success("✅ Đã lưu cấu hình thành công! Hãy chạy file test_telegram.py để kiểm tra kết nối.")
            st.toast("✅ Đã lưu cấu hình!")
