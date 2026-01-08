import streamlit as st
import pandas as pd
import requests
import re

def get_wikipedia_english(ja_name):
    """
    透過維基百科 API 獲取跨語言 (日文 -> 英文) 的標準藥名
    """
    if not ja_name or pd.isna(ja_name):
        return "N/A"

    # 清除括號備註
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(ja_name)).strip()
    
    # 處理複合藥
    if '･' in clean_ja or '・' in clean_ja:
        parts = re.split(r'[･・]', clean_ja)
        return " / ".join([get_wikipedia_english(p) for p in parts])

    try:
        # 1. 先用日文搜尋維基百科頁面
        search_url = "https://ja.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "prop": "langlinks",
            "titles": clean_ja,
            "lllang": "en",
            "format": "json",
            "redirects": 1
        }
        resp = requests.get(search_url, timeout=5).json()
        
        # 2. 提取英文頁面標題 (這通常就是標準英文藥名)
        pages = resp.get("query", {}).get("pages", {})
        for pg_id in pages:
            langlinks = pages[pg_id].get("langlinks", [])
            if langlinks:
                return langlinks[0].get("*")
        
        return f"Check: {clean_ja}"
    except:
        return f"Error: {clean_ja}"

# --- UI 介面 ---
st.title("📚 維基百科跨語言對照引擎 (505項終極版)")
st.info("利用維基百科的多語關聯性，將日文藥名直接對應到國際標準英文名。")

f = st.file_uploader("上傳 CSV 檔案", type=['csv'])

if f:
    df = pd.read_csv(f)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    if st.button("🚀 啟動維基百科全量對照"):
        with st.spinner('正在檢索跨語言數據庫，這可能需要幾分鐘...'):
            df['成分英文名'] = df['成分日文名'].apply(get_wikipedia_english)
            df['來源'] = "Wikipedia_Cross_Lingual"
            
        st.success("✅ 對照完畢！")
        st.dataframe(df)
        
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載最終對照版 CSV", csv_data, "Medicine_Wikipedia_Result.csv")
