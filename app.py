import streamlit as st
import pandas as pd
import requests
import re
import time
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 1. 配置區域 ---
AZURE_KEY = "9JDF24qrsW8rXiYmChS17yEPyNRI96nNXXqEKn5CyI6ql6iYcTOFJQQJ99BLAC3pKaRXJ3w3AAAbACOGVYVU"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_REGION = "eastasia"

def get_english_test(jp_name):
    """ 測試專用：Wikipedia -> KEGG -> Azure 三層檢索 """
    if not jp_name or pd.isna(jp_name): return "N/A", "Skip"
    
    # 強力清洗日文 (移除括號、水和物、鹽類)
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(jp_name)).strip()
    clean_ja = re.sub(r'(水和物|塩酸塩|カリウム|ナトリウム|臭化物|エステル)$', '', clean_ja)

    # 1. Wikipedia API (最快且對片假名最準)
    try:
        w_url = f"https://ja.wikipedia.org/w/api.php?action=query&titles={quote(clean_ja)}&prop=langlinks&lllang=en&format=json"
        w_res = requests.get(w_url, timeout=5).json()
        pages = w_res.get('query', {}).get('pages', {})
        for p in pages.values():
            if 'langlinks' in p:
                return p['langlinks'][0]['*'], "Wikipedia"
    except: pass

    # 2. KEGG Medicus (官方藥典)
    try:
        search_url = f"https://www.kegg.jp/medicus-bin/search_drug?search_keyword={quote(clean_ja)}"
        r = requests.get(search_url, timeout=5)
        codes = re.findall(r'japic_code=(\d+)', r.text + r.url)
        if codes:
            ri = requests.get(f"https://www.kegg.jp/medicus-bin/japic_med?id={codes[0].zfill(8)}")
            ri.encoding = 'shift_jis'
            soup = BeautifulSoup(ri.text, 'html.parser')
            th = soup.find('th', string=re.compile(r'欧文一般名'))
            if th and th.find_next_sibling('td'):
                return th.find_next_sibling('td').get_text(strip=True), "KEGG"
    except: pass

    # 3. Azure (最後手段)
    try:
        url = f"{AZURE_ENDPOINT.strip('/')}/translate?api-version=3.0&from=ja&to=en"
        headers = {'Ocp-Apim-Subscription-Key': AZURE_KEY, 'Ocp-Apim-Subscription-Region': AZURE_REGION, 'Content-type': 'application/json'}
        res = requests.post(url, headers=headers, json=[{'text': clean_ja}], timeout=5)
        if res.status_code == 200:
            return res.json()[0]['translations'][0]['text'], "Azure"
    except: pass

    return "[對照失敗]", "None"

# --- 2. UI 測試介面 ---
st.title("🧪 前 10 項對照壓力測試")

f = st.file_uploader("上傳 2026-01-08T06-33_export.csv", type=['csv'])

if f:
    df_all = pd.read_csv(f)
    test_df = df_all.head(10).copy() # 只取前 10 項
    
    st.write("🔍 **預計測試的前 10 項日文成分：**")
    st.write(", ".join(test_df["成分日文名"].tolist()))

    if st.button("🚀 開始測試前 10 項"):
        results = []
        bar = st.progress(0)
        for i, row in test_df.iterrows():
            jp = row["成分日文名"]
            en, src = get_english_test(jp)
            results.append({"成分日文名": jp, "成分英文名": en, "對照來源": src})
            bar.progress((i + 1) / 10)
        
        res_df = pd.DataFrame(results)
        st.success("✅ 測試完成！請檢查下方對照結果：")
        st.table(res_df) # 使用表格顯示更清晰

        # 判斷成功率
        success_count = len(res_df[res_df["對照來源"] != "None"])
        if success_count >= 8:
            st.balloons()
            st.info(f"成功率 {success_count}/10，建議可以執行全量對照。")
        else:
            st.warning(f"成功率僅 {success_count}/10，可能需要調整清洗邏輯。")
