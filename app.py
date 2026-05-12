import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 網頁基礎設定 ---
st.set_page_config(page_title="台股千金戰略觀測站", page_icon="🏆", layout="wide")
st.title("🏆 台股千金與潛力股戰略儀表板")
st.markdown("此工具每日自動抓取最新收盤數據，並為您自動分類為「破千軍」、「預備軍」與「潛力股」。")

# --- 核心抓取邏輯 ---
def get_twse_data():
    yesterday = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y%m%d') 
    
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&date={yesterday_str}&type=ALLBUT0999"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers, verify=False)
    data = res.json()
    
    if data.get('stat') != 'OK':
        raise Exception(f"證交所目前無 {yesterday_str} 的資料，原因: {data.get('stat')} (可能為假日休市)")
    
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
    
    # 確保欄位存在才提取，避免因證交所改名而報錯
    existing_cols = [c for c in cols_to_keep if c in df.columns]
    df = df[existing_cols]
    
    return df, yesterday_str

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

# --- 網頁互動區塊 ---
if st.button("🔄 點擊獲取最新台股分類", type="primary"):
    with st.spinner('正在連線至台灣證券交易所，解析最新數據中...'):
        try:
            df, data_date = get_twse_data()
            
            # 1. 資料清洗
            df['收盤價'] = df['收盤價'].str.replace(',', '', regex=False).replace('--', '0', regex=False)
            df['收盤價'] = pd.to_numeric(df['收盤價'], errors='coerce')
            
            # 2. 寫入戰略分類標籤
            df['戰略分類'] = df['收盤價'].apply(classify_stock)
            
            # 3. 依收盤價由高至低排序
            df_sorted = df.sort_values(by='收盤價', ascending=False)
            
            st.success(f"✅ 資料載入成功！目前的數據日期為：{data_date}")
            
            # 4. 建立網頁視覺化頁籤 (Tabs)
            tab1, tab2, tab3, tab4 = st.tabs(["🏆 破千軍", "⭐ 破千預備軍", "🔥 破千潛力股", "📋 完整市場清單"])
            
            with tab1:
                st.subheader("🏆 破千軍 (股價 1000 元以上)")
                df_1000 = df_sorted[df_sorted['收盤價'] >= 1000]
                st.dataframe(df_1000, use_container_width=True, height=400)
                
            with tab2:
                st.subheader("⭐ 破千預備軍 (股價 900 ~ 999 元)")
                df_900 = df_sorted[(df_sorted['收盤價'] >= 900) & (df_sorted['收盤價'] < 1000)]
                st.dataframe(df_900, use_container_width=True, height=400)
                
            with tab3:
                st.subheader("🔥 破千潛力股 (此處以股價 700 ~ 899 元為觀測指標)")
                df_700 = df_sorted[(df_sorted['收盤價'] >= 700) & (df_sorted['收盤價'] < 900)]
                st.dataframe(df_700, use_container_width=True, height=400)
                
            with tab4:
                st.subheader("📋 完整市場清單")
                st.dataframe(df_sorted, use_container_width=True, height=600)
            
        except Exception as e:
            st.error(f"發生錯誤: {e}")

st.divider()
st.caption("Powered by Streamlit | Data Source: TWSE 台灣證券交易所")
