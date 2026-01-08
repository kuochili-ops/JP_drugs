import streamlit as st
import pandas as pd
import requests
import re
from googlesearch import search  # 需要 pip install googlesearch-python
from bs4 import BeautifulSoup

def find_japic_code_and_name(ja_name):
    """
    自動化核心：搜尋 Google 並從網址中提取 JAPIC Code，再向 KEGG 請求
    """
    if not ja_name or pd.isna(ja_name):
        return "N/A", "N/A"

    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(ja_name)).strip()
    query = f"{clean_ja} japic"
    
    try:
        # 1. 自動搜尋 Google 並獲取前 3 個結果
        for url in search(query, num_results=3):
            # 2. 從網址中偵測 8 位數字的 JAPIC Code
            # 網址格式通常含有 japic_code=00051825
            match = re.search(r'japic_code=(\d{8})', url)
            if match:
                japic_code = match.group(1)
                
                # 3. 拿到 Code 後，直接向 KEGG API 請求標準英文名
                kegg_url = f"https://www.kegg.jp/medicus-bin/japic_med?japic_code={japic_code}"
                resp = requests.get(kegg_url, timeout=5)
                resp.encoding = 'utf-8'
                
                if resp.status_code == 200:
                    # 提取「一般名」後的英文
                    content = resp.text
                    # 匹配格式如：一般名 (Midazolam) 或 [JAN:Midazolam]
                    en_match = re.search(r'一般名.*?\((.*?)\)', content)
                    if en_match:
                        return japic_code, en_match.group(1).split(';')[0].strip()
        
        return "Not Found", "Manual Check"
    except Exception as e:
        return "Error", str(e)

# --- UI ---
st.set_page_config(layout="wide")
st.title("🤖 505項全自動 JAPIC 偵測引擎")
st.info("本引擎會模擬您的操作：自動搜尋 Google -> 提取 JAPIC Code -> 抓取官方英文名。")

f = st.file_uploader("上傳 2026-01-08T08-01_export.csv", type=['csv'])

if f:
    df = pd.read_csv(f)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed|來源|成分英文名')]
    
    if st.button("🚀 啟動全自動偵測 (預計 5-10 分鐘)"):
        japic_codes = []
        english_names = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, row in df.iterrows():
            name = row['成分日文名']
            status_text.text(f"正在掃描第 {i+1}/505 項: {name}")
            
            code, en = find_japic_code_and_name(name)
            japic_codes.append(code)
            english_names.append(en)
            
            progress_bar.progress((i + 1) / len(df))
            
        df['JAPIC_Code'] = japic_codes
        df['成分英文名'] = english_names
        df['來源'] = "Auto_JAPIC_Crawler"
        
        st.success("✅ 全量掃描完成！")
        st.dataframe(df)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載全自動校正版 CSV", csv, "Medicine_JAPIC_Auto_Final.csv")
