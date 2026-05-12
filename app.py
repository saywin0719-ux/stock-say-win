import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 網頁基礎設定 ---
st.set_page_config(page_title="台股千金戰略觀測站", page_icon="🏆", layout="wide")
st.title("🏆 台股千金與潛力股戰略儀表板 (全市場版)")
st.markdown("觀測範圍包含 **上市 (TWSE) 與 上櫃 (TPEx)** 全市場。系統將自動為您抓取最新數據，並分類為「破千軍」、「預備軍」與「潛力股」。")

tw_timezone = timezone(timedelta(hours=8))
tw_now = datetime.now(tw_timezone)

col1, col2 = st.columns([1, 3])
with col1:
    selected_date = st.date_input(
        "📅 請選擇上市觀測日期", 
        value=tw_now.date(),
        max_value=tw_now.date()
    )

# --- 1. 抓取上市 (TWSE) 邏輯 ---
def get_twse_data(date_obj):
    date_str = date_obj.strftime('%Y%m%d')
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&date={date_str}&type=ALLBUT0999"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers, verify=False)
    data = res.json()
    
    if data.get('stat') != 'OK':
        return pd.DataFrame(columns=['證券代號', '證券名稱', '收盤價', '成交股數', '市場'])
    
    target_fields, target_data = None, None
    if 'tables' in data:
        for table in data['tables']:
            fields = table.get('fields', [])
            if '證券代號' in fields and '收盤價' in fields:
                target_fields = fields
                target_data = table.get('data', [])
                break
                
    if not target_fields or not target_data:
         return pd.DataFrame(columns=['證券代號', '證券名稱', '收盤價', '成交股數', '市場'])
         
    df = pd.DataFrame(target_data, columns=target_fields)
    cols_to_keep = ['證券代號', '證券名稱', '收盤價', '成交股數']
    df = df[[c for c in cols_to_keep if c in df.columns]]
    df['市場'] = '上市'
    return df

# --- 2. 抓取上櫃 (TPEx) 邏輯 (政府 OpenAPI 防彈容錯版) ---
def get_tpex_data():
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = requests.get(url, headers=headers, verify=False, timeout=10)
        data = res.json()
        
        if not data:
            return pd.DataFrame(columns=['證券代號', '證券名稱', '收盤價', '成交股數', '市場'])
            
        df = pd.DataFrame(data)
        df_tpex = pd.DataFrame()
        
        # 【防彈機制 1】使用 df.get()：即使政府改了欄位名稱，也不會報錯，只會回傳空白
        df_tpex['證券代號'] = df.get('SecuritiesCompanyCode', df.get('Code', ''))
        df_tpex['證券名稱'] = df.get('CompanyName', df.get('Name', ''))
        df_tpex['收盤價'] = df.get('Close', df.get('ClosePrice', '0'))
        
        # 【防彈機制 2】多重探測成交量欄位：如果 A 不在，就找 B，最後補 0
        if 'TradingVolume' in df.columns:
            df_tpex['成交股數'] = df['TradingVolume']
        elif 'TradingShares' in df.columns:
            df_tpex['成交股數'] = df['TradingShares']
        elif 'TradeVolume' in df.columns:
            df_tpex['成交股數'] = df['TradeVolume']
        else:
            df_tpex['成交股數'] = '0'  # 找不到量也沒關係，保證程式繼續活著
            
        df_tpex['市場'] = '上櫃'
        
        return df_tpex
        
    except Exception as e:
        st.error(f"❌ 上櫃 OpenAPI 資料取得失敗：{e}")
        # 如果真的出錯，顯示出政府現在到底給了什麼欄位，方便我們未來除錯
        if 'df' in locals():
            st.warning(f"目前政府 API 實際提供的欄位有：{list(df.columns)}")
        return pd.DataFrame(columns=['證券代號', '證券名稱', '收盤價', '成交股數', '市場'])
        
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
if st.button("🔄 開始分析全市場數據", type="primary"):
    with st.spinner('正在向證交所與官方 OpenAPI 請求最新數據...'):
        try:
            # 兵分兩路抓取資料
            df_twse = get_twse_data(selected_date)
            df_tpex = get_tpex_data() # OpenAPI 預設抓取市場最新資料
            
            # 合併上市與上櫃資料
            df_all = pd.concat([df_twse, df_tpex], ignore_index=True)
            
            if df_all.empty:
                st.warning("⚠️ 查無資料，可能遇週末休市或 API 維護中。")
            else:
                # 資料清洗與型別轉換
                df_all['收盤價'] = df_all['收盤價'].astype(str).str.replace(',', '', regex=False).str.replace('--', '0', regex=False)
                df_all['收盤價'] = pd.to_numeric(df_all['收盤價'], errors='coerce')
                
                # 寫入戰略分類標籤並排序
                df_all['戰略分類'] = df_all['收盤價'].apply(classify_stock)
                df_sorted = df_all.sort_values(by='收盤價', ascending=False)
                
                st.success(f"✅ 全市場資料載入成功！")
                
                # 建立網頁視覺化頁籤
                tab1, tab2, tab3, tab4 = st.tabs(["🏆 破千軍", "⭐ 破千預備軍", "🔥 破千潛力股", "📋 全市場完整清單"])
                
                with tab1:
                    st.subheader("🏆 破千軍 (包含上市與上櫃)")
                    st.dataframe(df_sorted[df_sorted['收盤價'] >= 1000], use_container_width=True, height=400)
                    
                with tab2:
                    st.subheader("⭐ 破千預備軍 (900 ~ 999 元)")
                    st.dataframe(df_sorted[(df_sorted['收盤價'] >= 900) & (df_sorted['收盤價'] < 1000)], use_container_width=True, height=400)
                    
                with tab3:
                    st.subheader("🔥 破千潛力股 (700 ~ 899 元)")
                    st.dataframe(df_sorted[(df_sorted['收盤價'] >= 700) & (df_sorted['收盤價'] < 900)], use_container_width=True, height=400)
                    
                with tab4:
                    st.subheader("📋 完整市場清單")
                    st.dataframe(df_sorted, use_container_width=True, height=600)
                
        except Exception as e:
            st.error(f"發生未預期的錯誤: {e}")

st.divider()
st.caption("Powered by Streamlit | Data Sources: TWSE (上市) & TPEx OpenAPI (上櫃)")
