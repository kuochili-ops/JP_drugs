import streamlit as st
import pandas as pd
import requests
import re
import time
import io
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 1. 配置區域 ---
AZURE_KEY = "9JDF24qrsW8rXiYmChS17yEPyNRI96nNXXqEKn5CyI6ql6iYcTOFJQQJ99BLAC3pKaRXJ3w3AAAbACOGVYVU"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_REGION = "eastasia"

# --- 2. 核心增強翻譯邏輯 ---

def clean_japanese_name(name):
    """ 強力清洗日文名，只保留核心成分 """
    if not name or pd.isna(name): return ""
    # 1. 移除括號及其內容 (如：(水和物)、（ベネトリン）)
    name = re.sub(r'[\(\（].*?[\)\）]', '', str(name))
    # 2. 移除常見後綴以提高 API 命中率
    suffixes = ['水和物', '塩酸塩', 'カリウム', 'ナトリウム', 'エステル', '臭化物']
    for s in suffixes:
        name = name.replace(s, '')
    return name.strip()

def get_translation_v2(jp_name):
    """ 
    多重補完策略：
    1. Azure 翻譯 (最快)
    2. Wikipedia 日英對照 (極準)
    3. KEGG 官方資料庫 (最權威)
    """
    if not jp_name or pd.isna(jp_name): return "N/A", "Skip"
    
    clean_ja = clean_japanese_name(jp_name)
    if not clean_ja: return "N/A", "Skip"

    # --- Step 1: Wikipedia API (日語轉英語，對藥名極其有效) ---
    try:
        wiki_url = f"https://ja.wikipedia.org/w/api.php?action=query&titles={quote(clean_ja)}&prop=langlinks&lllang=en&format=json"
        wiki_res = requests.get(wiki_url, timeout=5).json()
        pages = wiki_res.get('query', {}).get('pages', {})
        for p in pages.values():
            if 'langlinks' in p:
                return p['langlinks'][0]['*'], "Wikipedia"
    except: pass

    # --- Step 2: Azure Translator ---
    try:
        url = f"{AZURE_ENDPOINT.strip('/')}/translate?api-version=3.0&from=ja&to=en"
        headers = {'Ocp-Apim-Subscription-Key': AZURE_KEY, 'Ocp-Apim-Subscription-Region': AZURE_REGION, 'Content-type': 'application/json'}
        res = requests.post(url, headers=headers, json=[{'text': clean_ja}], timeout=5)
        if res.status_code == 200:
            en = res.json()[0]['translations'][0]['text']
            if len(en) > 2: return en, "Azure"
    except: pass

    # --- Step 3: KEGG Fallback ---
    try:
        search_url = f"https://www.kegg.jp/medicus-bin/search_drug?search_keyword={quote(clean_ja)}"
        r = requests.get(search_url, timeout=10)
        codes = re.findall(r'japic_code=(\d+)', r.text + r.url)
        if codes:
            ri = requests.get(f"https://www.kegg.jp/medicus-bin/japic_med?id={codes[0].zfill(8)}")
            ri.encoding = 'shift_jis' # KEGG 常使用 SJIS 或 EUC-JP
            soup = BeautifulSoup(ri.text, 'html.parser')
            th = soup.find('th', string=re.compile(r'欧文一般名'))
            if th and th.find_next_sibling('td'):
                return th.find_next_sibling('td').get_text(strip=True), "KEGG"
    except: pass

    return "[仍未找到]", "None"

# --- 3. Streamlit UI ---
st.set_page_config(layout="wide", page_title="505項補完 V2")
st.title("💊 醫藥品清單補完 (Wikipedia + Azure + KEGG)")

# 上傳您剛下載的那個 CSV
f = st.file_uploader("請上傳剛才失敗的 2026-01-08T06-16_export.csv", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 移除舊的索引列 (如果有)
    if 'Unnamed: 0' in df.columns: df = df.drop(columns=['Unnamed: 0'])
    
    st.write(f"📊 目前清單項目：{len(df)}")
    st.dataframe(df.head(10), use_container_width=True)

    if st.button("🚀 執行終極補全計畫"):
        bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            # 只處理「仍未找到」或資料來源為 None 的項
            curr_en = str(row["成分英文名"])
            if curr_en in ["[仍未找到]", "None", "nan", ""]:
                jp_name = row["成分日文名"]
                status.text(f"正在深度檢索 ({i+1}/{len(df)}): {jp_name}")
                
                en_name, source = get_translation_v2(jp_name)
                df.at[i, "成分英文名"] = en_name
                df.at[i, "來源"] = source
            
            bar.progress((i + 1) / len(df))
            if i % 10 == 0: time.sleep(0.05)
            
        st.success("🎉 全量修補完成！")
        st.dataframe(df, use_container_width=True)
        
        # 匯出 CSV (UTF-8-SIG 確保 Excel 不亂碼)
        csv_out = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載終極修正報告", csv_out, "Medicine_Final_Fixed.csv")
