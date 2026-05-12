import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 網頁基礎設定 ---
st.set_page_config(page_title="台股千金戰略觀測站", page_icon="🏆", layout="wide")
st.title("🏆 台股千金與潛力股戰略儀表板")
st.markdown("請在下方選擇您想觀測的交易日。系統將自動為您抓取數據，並分類為「破千軍」、「預備軍」與「潛力股」。")

# --- 取得台灣當地時間 (UTC+8) ---
tw_timezone = timezone(timedelta(hours=8))
tw_now = datetime.now(tw_timezone)

# --- 互動式日曆選擇器 ---
# 預設顯示台灣時間的「今天」 (如果今天還沒收盤，您可以手動點選昨天或上週五)
col1, col2 = st.columns([1, 3])
with col1:
    selected_date = st.date_input(
        "📅 請選擇交易日期", 
        value=tw_now.date(),
        max_value=tw_now.date() # 限制最多只能選到今天，防止選到未來
    )

# 將選好的日期轉換為證交所需要的 YYYYMMDD 格式
query_date_str = selected_date.strftime('%Y%m%d')

# --- 核心抓取邏輯 (接收使用者選定的日期) ---
def get_twse_data(date_str):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&date={date_str}&type=ALLBUT0999"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers, verify=False)
    data = res.json()
    
    if data.get('stat') != 'OK':
        raise Exception(f"證交所目前無 {date_str} 的資料，原因: {data.get('stat')} (可能為週末或國定假日)")
    
    target_fields, target_data = None, None
    if 'tables' in data:
        for table in data['tables']:
            fields = table.get('fields', [])
            if '證券代號' in fields and '收盤價' in fields:
                target_fields = fields
                target_data = table.get('data', [])
                break
                
    if not target_fields or not target_data:
         raise Exception("資料結構改版，無法找到正確的股票表格！")
         
    df = pd.DataFrame(target_data, columns=target_fields)
    cols_to_keep = ['證券代號', '證券名稱', '收盤價', '漲跌幅', '成交股數']
    
    existing_cols = [c for c in cols_to_keep if c in df.columns]
    df = df[existing_cols]
    
    return df

# --- 分類邏輯函數 ---
def classify_stock(price):
    if pd.isna(price):
        return "無資料"
    elif price >= 1000:
        return "🏆 破千軍 (>=1000)"
    elif price >= 900:
        return "⭐ 破千預備軍 (900~999)"
    elif price >= 700:
        return "🔥 破千潛力股 (700~899)"
    else:
        return "一般股"

# --- 網頁資料呈現區塊 ---
if st.button("🔄 開始分析該日數據", type="primary"):
    with st.spinner(f'正在向台灣證券交易所請求 {query_date_str} 的數據...'):
        try:
            # 傳入您選擇的日期
            df = get_twse_data(query_date_str)
            
            # 資料清洗
            df['收盤價'] = df['收盤價'].str.replace(',', '', regex=False).replace('--', '0', regex=False)
            df['收盤價'] = pd.to_numeric(df['收盤價'], errors='coerce')
            
            # 寫入戰略分類標籤
            df['戰略分類'] = df['收盤價'].apply(classify_stock)
            
            # 依收盤價排序
            df_sorted = df.sort_values(by='收盤價', ascending=False)
            
            st.success(f"✅ 資料載入成功！目前顯示的數據日期為：{query_date_str}")
            
            # 建立網頁視覺化頁籤
            tab1, tab2, tab3, tab4 = st.tabs(["🏆 破千軍", "⭐ 破千預備軍", "🔥 破千潛力股", "📋 完整市場清單"])
            
            with tab1:
                st.subheader("🏆 破千軍 (股價 1000 元以上)")
                st.dataframe(df_sorted[df_sorted['收盤價'] >= 1000], use_container_width=True, height=400)
                
            with tab2:
                st.subheader("⭐ 破千預備軍 (股價 900 ~ 999 元)")
                st.dataframe(df_sorted[(df_sorted['收盤價'] >= 900) & (df_sorted['收盤價'] < 1000)], use_container_width=True, height=400)
                
            with tab3:
                st.subheader("🔥 破千潛力股 (股價 700 ~ 899 元)")
                st.dataframe(df_sorted[(df_sorted['收盤價'] >= 700) & (df_sorted['收盤價'] < 900)], use_container_width=True, height=400)
                
            with tab4:
                st.subheader("📋 完整市場清單")
                st.dataframe(df_sorted, use_container_width=True, height=600)
            
        except Exception as e:
            # 如果遇到週末，會友善地在這裡顯示錯誤，提醒您換一天
            st.error(f"無法取得資料: {e} \n\n 💡 小提示：台股週末及國定假日不開盤，請嘗試選擇星期一至星期五的日期！")

st.divider()
st.caption("Powered by Streamlit | Data Source: TWSE 台灣證券交易所")
