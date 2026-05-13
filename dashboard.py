import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Đấu Thầu Analytics", page_icon="📊", layout="wide")

def load_data():
    conn = sqlite3.connect("bids.db")
    try:
        df = pd.read_sql_query("SELECT * FROM bids_full", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

st.title("📊 Bảng Điều Khiển Đấu Thầu (Data Warehouse)")

df = load_data()

if df.empty:
    st.warning("CSDL hiện chưa có dữ liệu. Vui lòng chạy Tool bằng giao diện hoặc Server để cào dữ liệu trước.")
    st.stop()

# Đổi tên cột cho đẹp
df = df.rename(columns={
    'ma_tbmt': 'Mã TBMT', 'ten': 'Tên gói thầu', 'chu_dau_tu': 'Chủ đầu tư',
    'linh_vuc': 'Lĩnh vực', 'gia_du_toan': 'Giá dự toán', 'hinh_thuc': 'Hình thức LCNT',
    'ngay_dang': 'Ngày đăng', 'dong_thau': 'Đóng thầu', 'dia_diem': 'Địa điểm',
    'link': 'Link chi tiết', 'diem_phu_hop': 'Điểm số', 'ai_summary': 'AI Đánh giá'
})

# Tính KPIs
total_bids = len(df)
potential_bids = len(df[df['Điểm số'] >= 3])
top_bids = len(df[df['Điểm số'] >= 4])

col1, col2, col3 = st.columns(3)
col1.metric("Tổng số gói thầu", total_bids)
col2.metric("Gói thầu liên quan (>=3⭐)", potential_bids)
col3.metric("Gói thầu TIỀM NĂNG (>=4⭐)", top_bids)

st.divider()

# Sidebar Lọc Dữ Liệu
st.sidebar.header("🔍 Bộ Lọc")
min_score = st.sidebar.slider("Chỉ hiển thị gói có điểm từ:", 0, 5, 0)
search_text = st.sidebar.text_input("Tìm kiếm (Tên gói, Chủ đầu tư):")

# Xử lý lọc
filtered_df = df[df['Điểm số'] >= min_score]
if search_text:
    filtered_df = filtered_df[
        filtered_df['Tên gói thầu'].str.contains(search_text, case=False, na=False) |
        filtered_df['Chủ đầu tư'].str.contains(search_text, case=False, na=False)
    ]

# Đồ thị Bar chart
try:
    date_counts = filtered_df['Ngày đăng'].str.extract(r'(\d{2}/\d{2}/\d{4})')[0].value_counts().reset_index()
    date_counts.columns = ['Ngày', 'Số lượng']
    date_counts = date_counts.sort_values('Ngày')
    if not date_counts.empty:
        fig = px.bar(date_counts, x='Ngày', y='Số lượng', title="Lưu lượng gói thầu theo ngày đăng", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    pass

st.subheader(f"📑 Danh sách gói thầu ({len(filtered_df)} kết quả)")

# Hiển thị dataframe
display_cols = ['Mã TBMT', 'Tên gói thầu', 'Chủ đầu tư', 'Giá dự toán', 'Ngày đăng', 'Điểm số']
st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)

st.subheader("🧠 Chi tiết AI Đánh Giá (Dành cho gói >=3⭐)")
if 'AI Đánh giá' not in filtered_df.columns:
    st.info("Chưa có dữ liệu AI. Hãy cập nhật Gemini API Key và quét lại.")
else:
    ai_df = filtered_df[filtered_df['AI Đánh giá'].notna() & (filtered_df['AI Đánh giá'] != "")]
    if ai_df.empty:
        st.info("Không có dữ liệu AI cho các gói thầu đang lọc.")
    else:
        for idx, row in ai_df.iterrows():
            with st.expander(f"{row['Điểm số']}⭐ - {row['Tên gói thầu']} (Chủ đầu tư: {row['Chủ đầu tư']})"):
                st.write(f"**💰 Giá dự toán:** {row['Giá dự toán']}")
                st.write(f"**📅 Ngày đăng:** {row['Ngày đăng']}")
                st.info(f"**🤖 AI Nhận xét:**\n\n{row['AI Đánh giá']}")
                st.markdown(f"[🔗 Xem chi tiết trên Mua sắm công]({row['Link chi tiết']})")
