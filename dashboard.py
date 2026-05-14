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
""", unsafe_allow_html=True)

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
        
    except Exception as e:
        df = pd.DataFrame()
    conn.close()
    return df

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

# ==========================================
# SIDEBAR LỌC DỮ LIỆU
# ==========================================
st.sidebar.header("🔍 CÔNG CỤ LỌC")

# 1. Lọc theo Từ khóa
search_text = st.sidebar.text_input("Tìm kiếm (Mã, Tên, Chủ đầu tư):", placeholder="Ví dụ: Mobifone...")

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

# 4. Lọc theo Lĩnh vực
all_fields = df['Lĩnh vực'].dropna().unique().tolist()
selected_fields = st.sidebar.multiselect("Lĩnh vực:", options=all_fields, default=all_fields)

st.sidebar.divider()
st.sidebar.caption("💡 Mẹo: Nhấn 'R' trên bàn phím để tải lại dữ liệu mới nhất.")

# Xử lý lọc Dataframe
filtered_df = df[df['Điểm số'] >= min_score]

start_dt = pd.to_datetime(start_d)
end_dt = pd.to_datetime(end_d) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
filtered_df = filtered_df[(filtered_df['Ngày_Date'] >= start_dt) & (filtered_df['Ngày_Date'] <= end_dt)]

if selected_fields:
    filtered_df = filtered_df[filtered_df['Lĩnh vực'].isin(selected_fields)]

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
tab1, tab2, tab3, tab4 = st.tabs(["📊 TỔNG QUAN", "🔍 DỮ LIỆU GÓI THẦU", "🤖 AI TRỢ LÝ", "🕵️ TÌNH BÁO ĐỐI THỦ"])

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
            st.plotly_chart(fig_line, use_container_width=True)
            
        with c2:
            # Phân bổ Lĩnh vực
            st.subheader("Cơ cấu Lĩnh vực")
            field_counts = filtered_df['Lĩnh vực'].value_counts().reset_index()
            field_counts.columns = ['Lĩnh vực', 'Số lượng']
            fig_pie = px.pie(field_counts, values='Số lượng', names='Lĩnh vực', hole=0.4, 
                             template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=350)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Bảng xếp hạng Chủ đầu tư
        st.subheader("Top 10 Chủ đầu tư Sôi động nhất")
        investor_counts = filtered_df['Chủ đầu tư'].value_counts().head(10).reset_index()
        investor_counts.columns = ['Chủ đầu tư', 'Số lượng']
        investor_counts = investor_counts.sort_values('Số lượng', ascending=True)
        fig_bar = px.bar(investor_counts, x='Số lượng', y='Chủ đầu tư', orientation='h',
                         template="plotly_dark", text_auto=True, color_discrete_sequence=['#F6AD55'])
        fig_bar.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=400)
        st.plotly_chart(fig_bar, use_container_width=True)
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
    display_cols = ['Mã TBMT', 'Tên gói thầu', 'Chủ đầu tư', 'Lĩnh vực', 'Giá dự toán', 'Ngày đăng', 'Điểm số', 'Link chi tiết']
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
