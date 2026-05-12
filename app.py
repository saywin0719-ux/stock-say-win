import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 網頁基礎設定 ---
st.set_page_config(page_title="台股量化觀測站", page_icon="📈", layout="wide")
st.title("📊 專屬台股收盤量化儀表板")
st.markdown("此工具每日自動抓取台灣證交所最新收盤數據，並依收盤價進行強度排序。")

# --- 核心抓取邏輯 (與前一版相同) ---
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
    cols_to_keep = ['證券代號', '證券名稱', '收盤價', '成交股數']
    df = df[cols_to_keep]
    
    return df, yesterday_str

# --- 網頁互動區塊 ---
# 建立一個點擊按鈕
if st.button("🔄 點擊獲取最新台股排序", type="primary"):
    # 顯示載入中的動畫
    with st.spinner('正在連線至台灣證券交易所，解析最新數據中...'):
        try:
            df, data_date = get_twse_data()
            
            # 資料清洗與轉換
            df['收盤價'] = df['收盤價'].str.replace(',', '', regex=False).replace('--', '0', regex=False)
            df['收盤價'] = pd.to_numeric(df['收盤價'], errors='coerce')
            
            # 依收盤價排序
            df_sorted = df.sort_values(by='收盤價', ascending=False)
            
            st.success(f"✅ 資料載入成功！目前的數據日期為：{data_date}")
            
            # 在網頁上直接顯示互動式資料表 (支援滾動、排序與放大)
            st.dataframe(
                df_sorted, 
                use_container_width=True,
                height=600
            )
            
        except Exception as e:
            st.error(f"發生錯誤: {e}")

st.divider()
st.caption("Powered by Streamlit | Data Source: TWSE")