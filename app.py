import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 網頁基礎設定 ---
st.set_page_config(page_title="台股千金戰略觀測站", page_icon="🏆", layout="wide")
st.title("🏆 台股千金與潛力股戰略儀表板 (全市場版)")
st.markdown("觀測範圍包含 **上市 (TWSE) 與 上櫃 (TPEx)** 全市場。系統將自動為您抓取數據，並分類為「破千軍」、「預備軍」與「潛力股」。")

tw_timezone = timezone(timedelta(hours=8))
tw_now = datetime.now(tw_timezone)

col1, col2 = st.columns([1, 3])
with col1:
    selected_date = st.date_input(
        "📅 請選擇交易日期", 
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
        return pd.DataFrame(columns=['證券代號', '證券名稱', '收盤價', '成交股數'])
    
    target_fields, target_data = None, None
    if 'tables' in data:
        for table in data['tables']:
            fields = table.get('fields', [])
            if '證券代號' in fields and '收盤價' in fields:
                target_fields = fields
                target_data = table.get('data', [])
                break
                
    if not target_fields or not target_data:
         return pd.DataFrame(columns=['證券代號', '證券名稱', '收盤價', '成交股數'])
         
    df = pd.DataFrame(target_data, columns=target_fields)
    cols_to_keep = ['證券代號', '證券名稱', '收盤價', '成交股數']
    df = df[[c for c in cols_to_keep if c in df.columns]]
    df['市場'] = '上市' # 加上市場標籤
    return df

# --- 2. 抓取上櫃 (TPEx) 邏輯 (終極強化版) ---
def get_tpex_data(date_obj):
    # 櫃買中心的日期格式要求為「民國年/月/日」
    tpex_year = date_obj.year - 1911
    tpex_date_str = f"{tpex_year}/{date_obj.strftime('%m/%d')}"
    
    # 【關鍵修復 1】網址必須加入 &o=json 才能正確取得數據
    url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=json&d={tpex_date_str}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = requests.get(url, headers=headers, verify=False, timeout=10)
        
        # 【關鍵修復 2】攔截非 JSON 格式的錯誤
        try:
            data = res.json()
        except:
            st.error("❌ 上櫃資料解析失敗：櫃買中心未回傳標準格式，可能 API 正在維護中。")
            return pd.DataFrame()
        
        # 如果當天沒有資料 (例如假日)
        if 'aaData' not in data or not data['aaData']:
            return pd.DataFrame()
            
        df = pd.DataFrame(data['aaData'])
        
        # 【關鍵修復 3】精準提取欄位，防範未來櫃買中心偷改欄位數量
        df_tpex = pd.DataFrame()
        df_tpex['證券代號'] = df[0]
        df_tpex['證券名稱'] = df[1]
        df_tpex['收盤價'] = df[2]
        # 若成交股數(第8欄)存在則抓取，否則補0避免當機
        df_tpex['成交股數'] = df[8] if df.shape[1] > 8 else '0' 
        df_tpex['市場'] = '上櫃'
        
        return df_tpex
        
    except Exception as e:
        # 【關鍵修復 4】把連線錯誤直接顯示在儀表板上，不再靜默失敗！
        st.error(f"❌ 上櫃伺服器連線異常：{e}")
        return pd.DataFrame()

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
    with st.spinner(f'正在向證交所與櫃買中心請求 {selected_date.strftime("%Y-%m-%d")} 的數據...'):
        try:
            # 分別抓取兩邊的資料
            df_twse = get_twse_data(selected_date)
            df_tpex = get_tpex_data(selected_date)
            
            # 將上市與上櫃資料垂直合併
            df_all = pd.concat([df_twse, df_tpex], ignore_index=True)
            
            if df_all.empty:
                st.warning("⚠️ 查無資料，該日可能為週末或國定假日休市。")
            else:
                # 資料清洗
                df_all['收盤價'] = df_all['收盤價'].astype(str).str.replace(',', '', regex=False).str.replace('--', '0', regex=False)
                df_all['收盤價'] = pd.to_numeric(df_all['收盤價'], errors='coerce')
                
                # 寫入戰略分類標籤
                df_all['戰略分類'] = df_all['收盤價'].apply(classify_stock)
                
                # 依收盤價排序
                df_sorted = df_all.sort_values(by='收盤價', ascending=False)
                
                st.success(f"✅ 全市場資料載入成功！目前顯示的數據日期為：{selected_date.strftime('%Y-%m-%d')}")
                
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
            st.error(f"無法取得資料: {e}")

st.divider()
st.caption("Powered by Streamlit | Data Sources: TWSE (上市) & TPEx (上櫃)")
